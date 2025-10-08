import asyncio
import sys
import importlib
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler


class SmartReloader(FileSystemEventHandler):
    """
    A file system event handler that intelligently reloads cogs or dependencies.
    - If a file in the 'cogs' directory is changed, it reloads that specific cog.
    - If a dependency file (e.g., a service or utility) is changed, it reloads
      that module and then reloads any cogs that depend on it.
    """

    def __init__(self, bot):
        self.bot = bot
        self.root_path = Path(__file__).parent.parent.resolve()
        self.cogs_folder_name = "cogs"

    def on_modified(self, event):
        if event.is_directory or not event.src_path.endswith(".py"):
            return

        path = Path(event.src_path).resolve()

        # Ignore changes to the reloader itself to prevent instability.
        if path == Path(__file__).resolve():
            print("INFO: Change detected in reloader.py, skipping reload.")
            return

        try:
            relative_path = path.relative_to(self.root_path)
        except ValueError:
            # File is outside the project directory.
            return

        if self.cogs_folder_name in relative_path.parts:
            cog_name = f"{self.cogs_folder_name}.{path.stem}"
            coro = self.reload_cog(cog_name)
            asyncio.run_coroutine_threadsafe(coro, self.bot.loop)
        else:
            module_name = ".".join(relative_path.with_suffix("").parts)
            coro = self.reload_dependency(module_name)
            asyncio.run_coroutine_threadsafe(coro, self.bot.loop)

    async def reload_cog(self, cog_name: str):
        """Handles the loading or reloading of a single cog."""
        try:
            if cog_name in self.bot.extensions:
                await self.bot.reload_extension(cog_name)
                print(f"Reloaded cog: {cog_name}")
            else:
                await self.bot.load_extension(cog_name)
                print(f"Loaded new cog: {cog_name}")
        except Exception as e:
            print(f"Failed to reload cog {cog_name}: {e}")

    async def reload_dependency(self, module_name: str):
        """Reloads a non-cog module and any cogs that import it."""
        if module_name not in sys.modules:
            print(f"INFO: Module {module_name} not yet loaded, skipping reload.")
            return

        try:
            module_obj = sys.modules[module_name]
            importlib.reload(module_obj)
            print(f"Reloaded dependency module: {module_name}")
        except Exception as e:
            print(f"Failed to reload dependency {module_name}: {e}")
            return

        cogs_to_reload = set()
        for cog_name, extension_module in self.bot.extensions.items():
            for attr in vars(extension_module).values():
                if hasattr(attr, "__module__") and attr.__module__ == module_name:
                    cogs_to_reload.add(cog_name)
                    break

        if not cogs_to_reload:
            print(f"INFO: No loaded cogs appear to depend on {module_name}.")
            return

        print(f"Reloading dependent cogs: {', '.join(cogs_to_reload)}")
        for cog_name in cogs_to_reload:
            await self.reload_cog(cog_name)


def start_watcher(bot):
    """Starts watching the project directory for file changes."""
    project_root = Path(__file__).parent.parent.resolve()
    event_handler = SmartReloader(bot)
    observer = Observer()
    observer.schedule(event_handler, str(project_root), recursive=True)
    observer.start()
    print(f"Hot-reloader is watching for file changes in: {project_root}")
    return observer
