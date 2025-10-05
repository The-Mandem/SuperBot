import asyncio
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler


class CogReloader(FileSystemEventHandler):
    def __init__(self, bot, cogs_folder: Path):
        self.bot = bot
        self.cogs_folder = cogs_folder

    def on_modified(self, event):
        if event.is_directory or not event.src_path.endswith(".py"):
            return

        path = Path(event.src_path)
        cog_name = f"{self.cogs_folder.name}.{path.stem}"

        asyncio.run_coroutine_threadsafe(self.reload_cog(cog_name), self.bot.loop)

    async def reload_cog(self, cog_name):
        try:
            if cog_name in self.bot.extensions:
                await self.bot.reload_extension(cog_name)
                print(f"Reloaded cog: {cog_name}")
            else:
                await self.bot.load_extension(cog_name)
                print(f"Loaded new cog: {cog_name}")
        except Exception as e:
            print(f"Failed to reload cog {cog_name}: {e}")


def start_watcher(bot, cogs_folder: Path):
    event_handler = CogReloader(bot, cogs_folder)
    observer = Observer()
    observer.schedule(event_handler, str(cogs_folder), recursive=False)
    observer.start()
    print("Watching for cog file changes...")
    return observer
