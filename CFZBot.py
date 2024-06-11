import discord
import json
import os
import asyncio
from discord.ext import commands
from discord import Intents, Interaction, Member
from discord.ext.commands import Bot
from discord import app_commands
from discord.utils import get

# Replace with your Discord bot token
TOKEN = 'MTI0NzIwNzAyNzYyMTQ5NDgyNA.G2iW7-.uV7kaBw0FuesqOPajVbK7tWMVo5e_Q-TJRuA44'

# Intents and Bot setup
intents = Intents.default()
intents.message_content = True
intents.members = True  # Intents for members required

bot = Bot(command_prefix='!', intents=intents)


# Function to calculate Elo ratings for individual players and teams
def calculate_elo(player1_rating, player2_rating, result, K=32):
    expected1 = 1 / (1 + 10**((player2_rating - player1_rating) / 400))
    expected2 = 1 / (1 + 10**((player1_rating - player2_rating) / 400))

    if result == 1:
        player1_rating += K * (1 - expected1)
        player2_rating += K * (0 - expected2)
    elif result == 0:
        player1_rating += K * (0 - expected1)
        player2_rating += K * (1 - expected2)
    else:
        player1_rating += K * (0.5 - expected1)
        player2_rating += K * (0.5 - expected2)

    return round(player1_rating), round(player2_rating)


def calculate_team_elo(team1_ratings, team2_ratings, result):
    team1_avg = sum(team1_ratings) / len(team1_ratings)
    team2_avg = sum(team2_ratings) / len(team2_ratings)

    new_team1_avg, new_team2_avg = calculate_elo(team1_avg, team2_avg, result)

    team1_deltas = [new_team1_avg - team1_avg] * len(team1_ratings)
    team2_deltas = [new_team2_avg - team2_avg] * len(team2_ratings)

    new_team1_ratings = [r + d for r, d in zip(team1_ratings, team1_deltas)]
    new_team2_ratings = [r + d for r, d in zip(team2_ratings, team2_deltas)]

    return new_team1_ratings, new_team2_ratings


# Functions for loading and saving Elo ratings
ELO_FILE_HESU = 'elo_ratings_hesu.json'
ELO_FILE_ZEQA = 'elo_ratings_zeqa.json'


def load_elo_ratings(filename):
    if os.path.exists(filename):
        with open(filename, 'r') as file:
            return json.load(file)
    else:
        return {}


def save_elo_ratings(ratings, filename):
    with open(filename, 'w') as file:
        json.dump(ratings, file)


elo_ratings_hesu = load_elo_ratings(ELO_FILE_HESU)
elo_ratings_zeqa = load_elo_ratings(ELO_FILE_ZEQA)

# Forbidden words and timeout duration
BANNED_WORDS = ['nigga', 'nga', 'niggas', 'suck', 'nigg']
TIMEOUT_DURATION = 60  # Timeout in seconds


# Event: Bot is ready
@bot.event
async def on_ready():
    print(f'Bot {bot.user} is online!')
    await bot.tree.sync()


# Custom Timeout Function
async def timeout_user(member: Member, duration: int, reason: str):
    captured_role = get(member.guild.roles, name="Prison")
    if not captured_role:
        # Create captured role if it doesn't exist
        captured_role = await member.guild.create_role(name="Prison")
        for channel in member.guild.channels:
            await channel.set_permissions(captured_role,
                                          speak=False,
                                          send_messages=False,
                                          read_message_history=True,
                                          read_messages=False)

    await member.add_roles(captured_role, reason=reason)
    await asyncio.sleep(duration)
    await member.remove_roles(captured_role, reason="Timeout expired")


# Event: Message received
@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    if any(banned_word in message.content.lower()
           for banned_word in BANNED_WORDS):
        await message.delete()
        await timeout_user(message.author, TIMEOUT_DURATION,
                           "Usage of a forbidden word")
        await message.channel.send(
            f'{message.author.mention} was jailed for using a bad word.')

    await bot.process_commands(message)


# Commands for Hesu
@bot.tree.command(name="elo_hesu",
                  description="Show your Elo rating for Hesu FBF.")
async def elo_hesu(interaction: Interaction, member: Member = None):
    member = member or interaction.user
    rating = elo_ratings_hesu.get(str(member.id), 1000)  # Default to 1000
    await interaction.response.send_message(
        f'{member.mention} has an Elo rating of {rating} for Hesu FireballFight.')


@bot.tree.command(
    name="match_hesu",
    description="Register a single match on Hesu and update Elo ratings")
async def match_hesu(interaction: Interaction, winner: Member, loser: Member):
    winner_rating = elo_ratings_hesu.get(str(winner.id), 1000)
    loser_rating = elo_ratings_hesu.get(str(loser.id), 1000)

    new_winner_rating, new_loser_rating = calculate_elo(
        winner_rating, loser_rating, 1)

    elo_ratings_hesu[str(winner.id)] = new_winner_rating
    elo_ratings_hesu[str(loser.id)] = new_loser_rating

    save_elo_ratings(elo_ratings_hesu, ELO_FILE_HESU)

    await interaction.response.send_message(
        f'New ratings Hesu - {winner.mention}: {new_winner_rating}, {loser.mention}: {new_loser_rating}'
    )


@bot.tree.command(
    name="team_match_hesu",
    description="Register a team match on Hesu and update Elo ratings")
@app_commands.describe(winner_team='Winner team members (mention)',
                       loser_team='Loser team members (mention)')
async def team_match_hesu(interaction: Interaction, winner_team: str,
                          loser_team: str):
    winner_team_members = [
        await bot.fetch_user(int(member_id.strip('<@!>')))
        for member_id in winner_team.split()
    ]
    loser_team_members = [
        await bot.fetch_user(int(member_id.strip('<@!>')))
        for member_id in loser_team.split()
    ]

    winner_ratings = [
        elo_ratings_hesu.get(str(member.id), 1000)
        for member in winner_team_members
    ]
    loser_ratings = [
        elo_ratings_hesu.get(str(member.id), 1000)
        for member in loser_team_members
    ]

    new_winner_ratings, new_loser_ratings = calculate_team_elo(
        winner_ratings, loser_ratings, 1)

    for member, new_rating in zip(winner_team_members, new_winner_ratings):
        elo_ratings_hesu[str(member.id)] = new_rating
    for member, new_rating in zip(loser_team_members, new_loser_ratings):
        elo_ratings_hesu[str(member.id)] = new_rating

    save_elo_ratings(elo_ratings_hesu, ELO_FILE_HESU)

    await interaction.response.send_message(
        f'New ratings on Hesu - Winner team: {[f"{member.mention}: {new_rating}" for member, new_rating in zip(winner_team_members, new_winner_ratings)]}, '
        f'Loser team: {[f"{member.mention}: {new_rating}" for member, new_rating in zip(loser_team_members, new_loser_ratings)]}'
    )


@bot.tree.command(name="leaderboard_hesu",
                  description="Show the Elo leaderboard for Hesu FireballFight (Top 10)")
async def leaderboard_hesu(interaction: Interaction):
    sorted_ratings = sorted(elo_ratings_hesu.items(),
                            key=lambda x: x[1],
                            reverse=True)
    top_10 = sorted_ratings[:10]
    leaderboard_message = "__**Elo Leaderboard of Hesu (Top 10)**__\n"

    for rank, (user_id, rating) in enumerate(top_10, start=1):
        member = await bot.fetch_user(int(user_id))
        leaderboard_message += f'**{rank}.** {member.mention}: **{rating}**\n'

    await interaction.response.send_message(leaderboard_message)


# Commands for Zeqa
@bot.tree.command(name="elo_zeqa", description="Show your Elo rating for Zeqa FBF.")
async def elo_zeqa(interaction: Interaction, member: Member = None):
    member = member or interaction.user
    rating = elo_ratings_zeqa.get(str(member.id), 1000)  # Default to 1000
    await interaction.response.send_message(
        f'{member.mention} has an Elo rating of {rating} for Zeqa FireballFight.')


@bot.tree.command(
    name="match_zeqa",
    description="Register a single match on Zeqa and update Elo ratings")
async def match_zeqa(interaction: Interaction, winner: Member, loser: Member):
    winner_rating = elo_ratings_zeqa.get(str(winner.id), 1000)
    loser_rating = elo_ratings_zeqa.get(str(loser.id), 1000)

    new_winner_rating, new_loser_rating = calculate_elo(
        winner_rating, loser_rating, 1)

    elo_ratings_zeqa[str(winner.id)] = new_winner_rating
    elo_ratings_zeqa[str(loser.id)] = new_loser_rating

    save_elo_ratings(elo_ratings_zeqa, ELO_FILE_ZEQA)

    await interaction.response.send_message(
        f'New ratings on Zeqa - {winner.mention}: {new_winner_rating}, {loser.mention}: {new_loser_rating}'
    )


@bot.tree.command(
    name="team_match_zeqa",
    description="Register a team match on Zeqa and update Elo ratings")
@app_commands.describe(winner_team='Winner team members (mention)',
                       loser_team='Loser team members (mention)')
async def team_match_zeqa(interaction: Interaction, winner_team: str,
                          loser_team: str):
    winner_team_members = [
        await bot.fetch_user(int(member_id.strip('<@!>')))
        for member_id in winner_team.split()
    ]
    loser_team_members = [
        await bot.fetch_user(int(member_id.strip('<@!>')))
        for member_id in loser_team.split()
    ]

    winner_ratings = [
        elo_ratings_zeqa.get(str(member.id), 1000)
        for member in winner_team_members
    ]
    loser_ratings = [
        elo_ratings_zeqa.get(str(member.id), 1000)
        for member in loser_team_members
    ]

    new_winner_ratings, new_loser_ratings = calculate_team_elo(
        winner_ratings, loser_ratings, 1)

    for member, new_rating in zip(winner_team_members, new_winner_ratings):
        elo_ratings_zeqa[str(member.id)] = new_rating
    for member, new_rating in zip(loser_team_members, new_loser_ratings):
        elo_ratings_zeqa[str(member.id)] = new_rating

    save_elo_ratings(elo_ratings_zeqa, ELO_FILE_ZEQA)

    await interaction.response.send_message(
        f'New ratings on Zeqa - Winner team: {[f"{member.mention}: {new_rating}" for member, new_rating in zip(winner_team_members, new_winner_ratings)]}, '
        f'Loser team: {[f"{member.mention}: {new_rating}" for member, new_rating in zip(loser_team_members, new_loser_ratings)]}'
    )


@bot.tree.command(name="leaderboard_zeqa",
                  description="Show the Elo leaderboard for FireballFight (Top 10)")
async def leaderboard_zeqa(interaction: Interaction):
    sorted_ratings = sorted(elo_ratings_zeqa.items(),
                            key=lambda x: x[1],
                            reverse=True)
    top_10 = sorted_ratings[:10]
    leaderboard_message = "__**Elo Leaderboard of Zeqa (Top 10)**__\n"

    for rank, (user_id, rating) in enumerate(top_10, start=1):
        member = await bot.fetch_user(int(user_id))
        leaderboard_message += f'**{rank}.** {member.mention}: **{rating}**\n'

    await interaction.response.send_message(leaderboard_message)


# Run the bot with the token
bot.run(TOKEN)
