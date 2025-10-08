from pathlib import Path
from config.manager import ConfigManager
from reloader.watcher import start_watcher


async def load_all_cogs(bot):
    """Load all cogs from the cogs directory."""
    cogs_folder = Path(__file__).parent.parent / "cogs"
    print("Loading cogs...")

    for file_path in cogs_folder.glob("*.py"):
        if not file_path.name.startswith("__"):
            try:
                await bot.load_extension(f"cogs.{file_path.stem}")
                print(f"Loaded cog: {file_path.name}")
            except Exception as e:
                print(f"Failed to load {file_path.name}: {e}")

    print("Cogs loaded successfully.")


def maybe_start_watcher(bot):
    """Start hot-reload watcher in development mode."""
    config = ConfigManager()
    if config.get_app_env() == "dev":
        start_watcher(bot)
