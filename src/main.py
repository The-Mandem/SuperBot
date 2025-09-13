from discord import Intents, Message
from discord.ext import commands
from config import ConfigManager
from features.instagram_feature import InstagramFeature
from features.gemini_feature import GeminiFeature
from features.rundown_feature import RundownFeature
from features.postman_feature import Postman
from features.bqq_feature import NoBqqFeature

intents: Intents = Intents.default()
intents.message_content = True


# We create a custom Bot class to override the setup_hook method.
# This is the recommended way to handle one-time async setup.
class MyBot(commands.Bot):
    async def setup_hook(self) -> None:
        """This hook is called once when the bot is setting up, before login."""
        print("Initializing features...")

        # Instagram Feature
        instagram_feature = InstagramFeature(self)
        await instagram_feature.setup()

        # Gemini Feature
        gemini_feature = GeminiFeature(self)
        await gemini_feature.setup()

        # Rundown Feature
        rundown_feature = RundownFeature(self)
        await rundown_feature.setup()

        # Postman/API caller Feature
        postman_feature = Postman(self)
        await postman_feature.setup()

        # Bqq feature
        bqq_feature = NoBqqFeature(self)
        await bqq_feature.setup()

        print("All features initialized and set up.")


bot = MyBot(command_prefix="!", intents=intents)


@bot.event
async def on_ready() -> None:
    """
    This event is called when the bot has successfully connected to Discord.
    It can be called multiple times (e.g., on reconnect), so one-time setup
    should not be placed here.
    """
    print(f"{bot.user} is now running!")


@bot.event
async def on_message(message: Message) -> None:
    config = ConfigManager()
    # Ignore messages from the bot itself to prevent loops
    if message.author == bot.user:
        return
    # Prod bot ignores tester channel
    tester_channel_id = config.get_tester_channel_id()
    if (
        tester_channel_id is not None
        and message.channel.id == tester_channel_id
        and config.get_app_env() == "prod"
    ):
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


if __name__ == "__main__":
    main()
