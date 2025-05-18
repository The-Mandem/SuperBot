from discord import Intents, Client, Message
from responses import get_response
from config import ConfigManager
from discord.ext import commands
import gemini

# STEP 1: BOT SETUP
intents: Intents = Intents.default()
intents.message_content = True  # NOQA
bot = commands.Bot(command_prefix="!", intents=intents)


# STEP 2: MESSAGE FUNCTIONALITY
async def send_message(message: Message, user_message: str) -> None:
    if not user_message:
        print('(Message was empty because intents were not enabled probably)')
        return

    try:
        await get_response(message)
    except Exception as e:
        print(e)


# STEP 3: HANDLING THE STARTUP FOR OUR BOT
@bot.event
async def on_ready() -> None:
    print(f'{bot.user} is now running!')


# STEP 4: HANDLING INCOMING MESSAGES
@bot.event
async def on_message(message: Message) -> None:
    if message.author == bot.user:
        return

    username = str(message.author)
    user_message = message.content
    channel = str(message.channel)

    print(f'[{channel}] {username}: "{user_message}"')

    await send_message(message, user_message)
    await bot.process_commands(message)


@bot.command(name="gemini")
async def gemini_command(ctx, *, prompt):
    response = gemini.gemini(prompt)
    if response:
        await ctx.send(response)
    else:
        await ctx.send("Error getting response.")



# STEP 5: MAIN ENTRY POINT
def main() -> None:
    config = ConfigManager()
    token = config.get_discord_token()
    bot.run(token)


if __name__ == '__main__':
    main()