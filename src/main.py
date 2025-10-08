from botcore.bot import MyBot
from config.manager import ConfigManager


def main():
    config = ConfigManager()
    try:
        token = config.get_discord_token()
        if not token:
            raise ValueError("Discord token not found.")

        bot = MyBot(command_prefix="!")
        bot.run(token)
    except Exception as e:
        print(f"Startup error: {e}")


if __name__ == "__main__":
    main()
