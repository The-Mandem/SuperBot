from discord.ext import commands
from discord import Intents
from botcore.loader import load_all_cogs, maybe_start_watcher
from botcore.event_filter import should_ignore_event


class MyBot(commands.Bot):
    def __init__(self, *args, **kwargs):
        intents = kwargs.pop("intents", Intents.default())
        intents.message_content = True
        super().__init__(*args, intents=intents, **kwargs)

    async def setup_hook(self):
        """Load cogs and start the dev watcher if needed."""
        await load_all_cogs(self)
        maybe_start_watcher(self)

    async def _run_event(self, coro, event_name, *args, **kwargs):
        """Universal event filter that ignores tester channel in prod."""
        if should_ignore_event(event_name, args):
            return
        await super()._run_event(coro, event_name, *args, **kwargs)
