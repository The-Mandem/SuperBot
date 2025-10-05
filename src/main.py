from pathlib import Path
from discord import Intents, Message
from discord.ext import commands
from config import ConfigManager
from reloader import start_watcher

intents: Intents = Intents.default()
intents.message_content = True


# We create a custom Bot class to override the setup_hook method.
# This is the recommended way to handle one-time async setup.
class MyBot(commands.Bot):
    async def setup_hook(self) -> None:
        print("Loading cogs...")
        cogs_folder = Path(__file__).parent / "cogs"
        for file_path in cogs_folder.glob("*.py"):
            if not file_path.name.startswith("__"):
                try:
                    await self.load_extension(f"{cogs_folder.name}.{file_path.stem}")
                    print(f"Successfully loaded cog: {file_path.name}")
                except Exception as e:
                    print(f"Failed to load cog {file_path.name}: {e}")
        print("All available cogs loaded.")

        config = ConfigManager()
        if config.get_app_env() == "dev":
            start_watcher(self)


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
    # Ignore messages from the bot itself to prevent loops
    if message.author == bot.user:
        return

    # Only log in development mode
    config = ConfigManager()
    if config.get_app_env() == "dev":
        username = str(message.author)
        user_message = message.content
        channel_name = str(message.channel)
        guild_name = str(message.guild.name) if message.guild else "DirectMessage"

        log_message = f'[{guild_name} - #{channel_name}] {username}: "{user_message}"'
        # Truncate long messages for cleaner logs
        if len(log_message) > 300:
            log_message = log_message[:297] + "..."
        print(log_message)

    # Process commands - essential for command handling
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
