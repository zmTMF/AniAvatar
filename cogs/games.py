import discord
import asyncio
import aiohttp
from discord import app_commands
from discord.ext import commands
import random
import json
import os

class Games(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.used_questions = set()
        self.data_path = os.path.join(os.path.dirname(__file__), "..", "data", "trivia.json")
        with open(self.data_path, "r", encoding="utf-8") as f:
            self.trivia_list = json.load(f)

    @commands.hybrid_command(name="animequiz", description="Start an anime trivia quiz.")
    @app_commands.describe(questions="Number of questions")
    @app_commands.choices(questions=[
        app_commands.Choice(name="5", value=5),
        app_commands.Choice(name="10", value=10),
        app_commands.Choice(name="15", value=15),
        app_commands.Choice(name="20", value=20),
    ])
    async def animequiz(self, ctx, questions: app_commands.Choice[int]):
        """Start an anime trivia quiz."""
        num_questions = questions.value

        quiz_questions = random.sample(self.trivia_list, min(num_questions, len(self.trivia_list)))
        score = 0

        for idx, question in enumerate(quiz_questions, 1):
            options_list = question["options"].copy()
            random.shuffle(options_list)
            options = [discord.SelectOption(label=opt, value=opt) for opt in options_list]

            async def callback(interaction: discord.Interaction):
                nonlocal score
                selected = interaction.data["values"][0]
                if selected == question["answer"]:
                    score += 1
                    await interaction.response.send_message(
                        f"✅ Correct! The answer is **{question['answer']}**.", ephemeral=True
                    )
                else:
                    await interaction.response.send_message(
                        f"❌ Wrong! The correct answer is **{question['answer']}**.", ephemeral=True
                    )
                select.disabled = True
                await message.edit(view=view)

            select = discord.ui.Select(placeholder="Choose an answer...", options=options)
            select.callback = callback
            view = discord.ui.View()
            view.add_item(select)

            message = await ctx.send(f"Question {idx}/{num_questions}: `{question['question']}`", view=view)

            def check(i):
                return i.message.id == message.id and i.user == ctx.author

            try:
                await self.bot.wait_for("interaction", check=check, timeout=15)
            except asyncio.TimeoutError:
                select.disabled = True
                await message.edit(view=view)
                await ctx.send(f"⏰ Time's up! The correct answer was `{question['answer']}`.")

        await ctx.send(f"🏁 Quiz finished! You scored **{score}/{num_questions}**.")
   
    @commands.hybrid_command(name="guesscharacter", description="Guess a random popular anime character")
    async def guesscharacter(self, ctx):
        """Guess a random popular anime character from AniList with multiple choice."""
        
        query = '''
        query ($page: Int, $perPage: Int) {
            Page(page: $page, perPage: $perPage) {
                characters(sort: FAVOURITES_DESC) {
                    id
                    name { full }
                    image { large }
                    media { nodes { title { romaji } } }
                }
            }
        }
        '''
        random_page = random.randint(1, 20)
        variables = {"page": random_page, "perPage": 50}

        async with aiohttp.ClientSession() as session:
            async with session.post("https://graphql.anilist.co", json={"query": query, "variables": variables}) as resp:
                if resp.status != 200:
                    return await ctx.send("❌ Couldn't fetch characters. Try again.")
                data = await resp.json()

        characters = data.get("data", {}).get("Page", {}).get("characters", [])
        if not characters:
            return await ctx.send("❌ Couldn't fetch characters. Try again.")

        character = random.choice(characters)
        correct_name = character["name"]["full"]
        image = character["image"]["large"]
        anime_nodes = character.get("media", {}).get("nodes", [])
        anime_title = anime_nodes[0]["title"]["romaji"] if anime_nodes else "Unknown Anime"

        other_characters = [c["name"]["full"] for c in characters if c["name"]["full"] != correct_name]
        fake_options = random.sample(other_characters, k=min(3, len(other_characters)))
        options_list = fake_options + [correct_name]
        random.shuffle(options_list)
        options = [discord.SelectOption(label=opt, value=opt) for opt in options_list]

        embed = discord.Embed(title="Guess the character!", description=f"From **{anime_title}**")
        embed.set_image(url=image)
        view = discord.ui.View()
        select = discord.ui.Select(placeholder="Choose the correct character...", options=options)
        view.add_item(select)

        async def callback(interaction: discord.Interaction):
            if interaction.user != ctx.author:
                await interaction.response.send_message("This is not your game!", ephemeral=True)
                return
            selected = interaction.data["values"][0]
            if selected == correct_name:
                await interaction.response.send_message(f"✅ Correct! It was **{correct_name}** from **{anime_title}**!")
            else:
                await interaction.response.send_message(f"❌ Wrong! The correct answer was **{correct_name}** from **{anime_title}**.")
            select.disabled = True
            await message.edit(view=view)

        select.callback = callback
        message = await ctx.send(embed=embed, view=view)

async def setup(bot):
    await bot.add_cog(Games(bot))
    print("📦 Loaded games cog.")
