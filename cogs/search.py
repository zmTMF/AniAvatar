import discord
from discord.ext import commands
from discord.ui import View, Select, Button
import aiohttp
import random
from urllib.parse import quote
import os
from dotenv import load_dotenv
import re

sent_image_cache = {}
anilist_cache = {}  # cache for characters
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
            await interaction.response.defer() # prevent interaction timeout
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

            await interaction.edit_original_response(embed=embed, view=None)

        select = Select(placeholder="Choose an anime...", options=options)
        select.callback = select_callback
        view = View()
        view.add_item(select)

        await ctx.send("Select an anime from the search results:", view=view)


    @commands.hybrid_command(name="animepfp", description="Get anime character PFP")
    @commands.guild_only()
    async def animepfp(self, ctx: commands.Context, *, name: str):
        name = (name or "").strip()
        if not name:
            return await ctx.send("❌ Please provide a character name.")

        NOISE_WORDS = {"pfp", "pfps", "hd", "avatar", "icon", "anime", "wallpaper", "image", "picture", "pic", "profile"}

        async def fetch_anilist_character(query_name: str):
            query_str = """
            query ($search: String) {
                Character(search: $search) {
                    id
                    name { full }
                    image { large medium }
                }
            }"""
            variables = {"search": query_name}
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(ANILIST_API, json={"query": query_str, "variables": variables}, timeout=10) as resp:
                        if resp.status != 200:
                            return None
                        data = await resp.json()
            except Exception:
                return None
            return data.get("data", {}).get("Character")

        original_query = name
        cleaned_words = [w for w in original_query.split() if w.lower() not in NOISE_WORDS]
        cleaned_query = " ".join(cleaned_words).strip() or original_query

        try:
            await ctx.defer()
        except Exception:
            pass

        char = await fetch_anilist_character(original_query)
        if not char and cleaned_query != original_query:
            char = await fetch_anilist_character(cleaned_query)

        if not char:
            return await ctx.send("❌ Could not find an anime character matching your query. Try a full character name (e.g. `Kaoruko Waguri`).")

        cache_key = f"al_{char['id']}"
        if cache_key not in anilist_cache:
            anilist_cache[cache_key] = {"anilist_images": [], "google": []}

        character_name = char["name"]["full"]
        official_image = (char.get("image") or {}).get("large") or (char.get("image") or {}).get("medium")

        selected_image = None
        source = None

        if official_image and official_image not in anilist_cache[cache_key]["anilist_images"]:
            selected_image = official_image
            anilist_cache[cache_key]["anilist_images"].append(official_image)
            source = "AniList"
        else:
            if not GOOGLE_API_KEY or not SEARCH_ENGINE_ID:
                return await ctx.send(f"❌ No new images available for **{character_name}** (Google API not configured).")

            search_query = f"{character_name} anime pfp"
            query = quote(search_query)
            url = (
                f"https://www.googleapis.com/customsearch/v1?"
                f"key={GOOGLE_API_KEY}&cx={SEARCH_ENGINE_ID}&searchType=image&q={query}"
            )

            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, timeout=10) as resp:
                        try:
                            data = await resp.json()
                        except Exception:
                            data = {}
            except Exception:
                return await ctx.send("❌ Failed to fetch images from Google API. Try again later.")

            items = data.get("items") or []
            valid_items = [
                item.get("link") for item in items
                if isinstance(item.get("link"), str) and item["link"].lower().endswith((".png", ".jpg", ".jpeg", ".webp"))
            ]

            if not valid_items:
                return await ctx.send(f"❌ No valid images found for **{character_name}** via Google.")

            unsent = [
                img for img in valid_items
                if img not in anilist_cache[cache_key]["google"] and img not in anilist_cache[cache_key]["anilist_images"]
            ]

            if not unsent:
                anilist_cache[cache_key]["google"] = []
                unsent = [img for img in valid_items if img not in anilist_cache[cache_key]["anilist_images"]]

            if not unsent:
                return await ctx.send(f"❌ No new images available for **{character_name}** right now.")

            selected_image = random.choice(unsent)
            anilist_cache[cache_key]["google"].append(selected_image)
            source = "Google API"

        # Send embed
        embed = discord.Embed(title=f"Anime PFP for {character_name}", color=discord.Color.purple())
        embed.set_image(url=selected_image)
        embed.set_footer(text=f"Source: {source}")
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Search(bot))
    print("📦 Loaded search cog.")

