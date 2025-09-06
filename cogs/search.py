import discord
from discord.ext import commands
from discord.ui import View, Select
import aiohttp
import random
from urllib.parse import quote
import os
from dotenv import load_dotenv
import re

sent_image_cache = {}
load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
SEARCH_ENGINE_ID = os.getenv("SEARCH_ENGINE_ID")

ANILIST_API = "https://graphql.anilist.co"


sent_media_cache = {}   

class Search(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name="anime", description="Search for an anime by name")
    @commands.guild_only()
    async def anime(self, ctx: commands.Context, *, query: str):
        """Fetch anime info from AniList GraphQL API"""

        query_str = """
        query ($search: String) {
        Page(perPage: 5) {
            media(search: $search, type: ANIME) {
            id
            title {
                romaji
                english
                native
            }
            description(asHtml: false)
            episodes
            status
            duration
            startDate { year month day }
            endDate { year month day }
            season
            averageScore
            popularity
            favourites
            format
            source
            studios(isMain: true) {
                nodes {
                name
                }
            }
            genres
            coverImage {
                large
                medium
            }
            bannerImage
            siteUrl
            }
        }
        }
        """

        variables = {"search": query}

        async with aiohttp.ClientSession() as session:
            async with session.post(ANILIST_API, json={"query": query_str, "variables": variables}) as resp:
                if resp.status != 200:
                    return await ctx.send("❌ Could not fetch anime info right now.")
                data = await resp.json()

        results = data.get("data", {}).get("Page", {}).get("media", [])
        if not results:
            return await ctx.send(f"❌ No results found for `{query}`.")

        options = []
        for anime in results:
            title = anime["title"]["english"] or anime["title"]["romaji"]
            episodes = anime.get("episodes") or "N/A"
            season = anime.get("season") or "N/A"
            options.append(discord.SelectOption(
                label=title[:100],
                description=f"Episodes: {episodes} | Season: {season}"[:100],
                value=str(anime["id"])
            ))

        async def select_callback(interaction: discord.Interaction):
            anime_id = int(interaction.data["values"][0])
            anime_data = next(a for a in results if a["id"] == anime_id)

            title = anime_data["title"]["english"] or anime_data["title"]["romaji"]
            url = anime_data.get("siteUrl")
            description = anime_data.get("description") or "No description available."
            description = description.replace("<br>", "\n").replace("<i>", "").replace("</i>", "")
            if len(description) > 4096:
                description = description[:4093] + "..."

            embed = discord.Embed(
                title=title,
                url=url,
                description=description,
                color=discord.Color.blurple()
            )

            if anime_data.get("coverImage", {}).get("medium"):
                embed.set_thumbnail(url=anime_data["coverImage"]["medium"])

            if anime_data.get("bannerImage"):
                embed.set_image(url=anime_data["bannerImage"])

            embed.add_field(name="Episodes", value=anime_data.get("episodes", "N/A"), inline=True)
            embed.add_field(name="Status", value=anime_data.get("status", "N/A").title(), inline=True)

            start = anime_data.get("startDate", {})
            end = anime_data.get("endDate", {})
            start_str = f"{start.get('year','N/A')}-{start.get('month','??')}-{start.get('day','??')}" if start.get("year") else "N/A"
            end_str = f"{end.get('year','N/A')}-{end.get('month','??')}-{end.get('day','??')}" if end.get("year") else "N/A"
            embed.add_field(name="Start Date", value=start_str, inline=True)
            embed.add_field(name="End Date", value=end_str, inline=True)

            embed.add_field(name="Duration", value=f"{anime_data.get('duration', 'N/A')} min/ep", inline=True)
            embed.add_field(name="Studio", value=anime_data["studios"]["nodes"][0]["name"] if anime_data["studios"]["nodes"] else "N/A", inline=True)
            embed.add_field(name="Source", value=anime_data.get("source", "N/A"), inline=True)

            embed.add_field(name="Score", value=f"{anime_data.get('averageScore', 'N/A')}%", inline=True)
            embed.add_field(name="Popularity", value=str(anime_data.get("popularity", "N/A")), inline=True)
            embed.add_field(name="Favourites", value=str(anime_data.get("favourites", "N/A")), inline=True)

            genres = anime_data.get("genres", [])
            if genres:
                genres = " ".join(f"`{g}`" for g in genres)
            else:
                genres = "N/A"

            embed.add_field(name="Genres", value=genres, inline=False)

            embed.set_footer(
                text="Provided by AniList",
                icon_url="https://anilist.co/img/icons/android-chrome-512x512.png"
            )

            await interaction.response.edit_message(embed=embed, view=None)

        select = Select(placeholder="Choose an anime...", options=options)
        select.callback = select_callback
        view = View()
        view.add_item(select)

        await ctx.send("Select an anime from the search results:", view=view)


    @commands.hybrid_command(name="animepfp", description="Get anime character PFP")
    @commands.guild_only()
    async def animepfp(self, ctx: commands.Context, *, name: str):
        name = name.strip()
        if not name:
            return await ctx.send("❌ Please provide a character name.")

        if "anime" not in name.lower():
            search_query = f"{name} anime character pfp"
        else:
            search_query = f"{name} pfp"
        
        query = quote(search_query)
        url = (
            f"https://www.googleapis.com/customsearch/v1?"
            f"key={GOOGLE_API_KEY}&cx={SEARCH_ENGINE_ID}&searchType=image&q={query}"
        )

        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                try:
                    data = await resp.json()
                except Exception:
                    return await ctx.send("❌ Failed to fetch data from Google API.")

        if "error" in data:
            return await ctx.send(f"❌ Google API Error: {data['error'].get('message','Unknown error')}")

        items = data.get("items", [])
        images = [item.get("link") for item in items if item.get("link", "").startswith("http")]

        if not images:
            return await ctx.send(
                f"❌ No valid images found for `{name}`.\n"
                "Try using the full character name or check spelling.\n"
                "Tip: Include the series name for better results (e.g., 'iuno wuwa' instead of just 'iuno')."
            )

        key = re.sub(r'\b(anime|pfp|character|photo|image|picture)\b', '', name.lower())
        key = re.sub(r'[^a-z0-9]', '', key).strip()
        
        if not key:
            key = name.lower()
        
        if key not in sent_image_cache:
            sent_image_cache[key] = []

        unsent = [img for img in images if img not in sent_image_cache[key]]

        if not unsent:
            sent_image_cache[key] = []
            unsent = images

        selected_image = random.choice(unsent)
        sent_image_cache[key].append(selected_image)

        if len(sent_image_cache[key]) > 20:
            sent_image_cache[key] = sent_image_cache[key][-10:]

        embed = discord.Embed(title=f"Anime PFP for {name}", color=discord.Color.purple())
        embed.set_image(url=selected_image)
        embed.set_footer(text="Tip: Use more specific terms for better results")
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Search(bot))
