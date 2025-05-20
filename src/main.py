from discord import Intents, Message
from discord.ext import commands
from config import ConfigManager
from features.instagram_feature import InstagramFeature
from features.gemini_feature import GeminiFeature
from features.postman_feature import Postman

intents: Intents = Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready() -> None:
    print(f'{bot.user} is now running!')

    # Instagram Feature
    instagram_feature = InstagramFeature(bot)
    await instagram_feature.setup()

    # Gemini Feature
    gemini_feature = GeminiFeature(bot)
    await gemini_feature.setup()

    #Postman/API caller Feature
    postman_feature = Postman(bot)
    await postman_feature.setup()
    
    # Bqq feature
    bqq_feature = bqq_feature(bot)
    await bqq_feature.setup()

    print("All features initialized and set up.")


@bot.event
async def on_message(message: Message) -> None:
    # Ignore messages from the bot itself to prevent loops
    if message.author == bot.user:
        return

    # Basic logging (can be expanded or moved to a dedicated logging module)
    username = str(message.author)
    user_message = message.content
    channel_name = str(message.channel)
    guild_name = str(message.guild.name) if message.guild else "DirectMessage"

    log_message = f'[{guild_name} - #{channel_name}] {username}: "{user_message}"'
    # Truncate long messages for cleaner logs
    if len(log_message) > 300:
        log_message = log_message[:297] + "..."
    print(log_message)

    await bot.process_commands(message)


def main() -> None:
    config = ConfigManager()
    try:
        discord_token = config.get_discord_token()
        if not discord_token:
            raise ValueError("Discord token is not available. Exiting.")
        bot.run(discord_token)
    except ValueError as e:
        print(f"CRITICAL CONFIGURATION ERROR: {e}")
    except Exception as e:
        print(f"An unexpected error occurred during bot startup or runtime: {e}")


if __name__ == '__main__':
    main()