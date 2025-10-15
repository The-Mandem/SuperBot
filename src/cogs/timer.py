# src/cogs/timer.py
from __future__ import annotations

import asyncio
import re
from typing import Optional, Tuple, Dict, Set

import discord
from discord.ext import commands

DURATION_RE = re.compile(
    r"^\s*(?:(\d+)\s*h)?\s*(?:(\d+)\s*m)?\s*(?:(\d+)\s*s)?\s*$", re.IGNORECASE
)


def parse_duration(raw: str) -> Tuple[int, str]:
    """
    Supports:
      - Single: 15m, 2h, 30s
      - Combo: 1h30m, 2m10s, 1h5s, 1h2m3s
      - Spaces are fine: '1h 30m', '45 m'
    Returns (total_seconds, human_string)
    Raises ValueError if invalid or zero.
    """
    raw = raw.strip()
    # If user passes only a number, assume minutes
    if raw.isdigit():
        raw = f"{raw}m"

    m = DURATION_RE.match(raw)
    if not m:
        raise ValueError(
            "Invalid duration. Use e.g. `15m`, `2h`, `45s`, or combos like `1h30m`."
        )

    h = int(m.group(1) or 0)
    mi = int(m.group(2) or 0)
    s = int(m.group(3) or 0)

    total = h * 3600 + mi * 60 + s
    if total <= 0:
        raise ValueError("Duration must be greater than zero.")

    parts = []
    if h:
        parts.append(f"{h} hour" + ("s" if h != 1 else ""))
    if mi:
        parts.append(f"{mi} minute" + ("s" if mi != 1 else ""))
    if s:
        parts.append(f"{s} second" + ("s" if s != 1 else ""))
    human = " ".join(parts) if parts else f"{total} seconds"

    # Optional guardrail
    MAX_SECONDS = 24 * 3600  # 24 hours
    if total > MAX_SECONDS:
        raise ValueError("Max timer is 24h. Try a smaller duration.")

    return total, human


class TimerCog(commands.Cog):
    """Simple timers: `!timer 15m [label]` → replies when done."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Track tasks per (channel_id, user_id) so we can cancel by user/channel
        self._active_tasks: Dict[tuple[int, int], Set[asyncio.Task]] = {}

    def cog_unload(self):
        # Cancel any outstanding timers on hot-reload/unload
        for task_set in list(self._active_tasks.values()):
            for t in list(task_set):
                t.cancel()
        self._active_tasks.clear()

    def _cancel_user_timers(self, channel_id: int, user_id: int) -> int:
        """Cancel all active timers for a given user in a given channel. Returns count canceled."""
        key = (channel_id, user_id)
        task_set = self._active_tasks.get(key)
        if not task_set:
            return 0
        count = 0
        for t in list(task_set):
            t.cancel()
            count += 1
        self._active_tasks.pop(key, None)
        return count

    async def _sleep_and_notify(
        self,
        channel: discord.abc.Messageable,
        mention: str,
        seconds: int,
        human: str,
        label: Optional[str],
        owner_channel_id: int,
        owner_user_id: int,
    ):
        try:
            await asyncio.sleep(seconds)
            # On completion, drop this task from the registry
            key = (owner_channel_id, owner_user_id)
            task_set = self._active_tasks.get(key)
            if task_set:
                # This coroutine corresponds to exactly one task; discard whichever is done.
                # The done_callback also cleans up, but we defensively prune here.
                for t in list(task_set):
                    if t.done():
                        task_set.discard(t)
                if not task_set:
                    self._active_tasks.pop(key, None)

            suffix = f" **({label})**" if label else ""
            await channel.send(f"{mention} ⏰ Time’s up{suffix}: **{human}** elapsed.")
        except asyncio.CancelledError:
            # Timer cancelled due to reload/shutdown or explicit cancel
            pass

    @commands.command(name="timer")
    async def timer_command(
        self, ctx: commands.Context, duration: str, *, label: str = ""
    ):
        """
        Start or cancel a timer and ping you when it finishes.
        Usage:
          !timer 15m
          !timer 1h30m
          !timer 45s take the cookies out
          !timer 45          # defaults to minutes
          !timer cancel      # cancels all your timers in this channel
        """
        # Handle cancellation
        if duration.lower() in {"cancel", "stop"}:
            canceled = self._cancel_user_timers(ctx.channel.id, ctx.author.id)
            if canceled:
                await ctx.reply(
                    f"🛑 Canceled **{canceled}** timer{'s' if canceled != 1 else ''} for you in this channel."
                )
            else:
                await ctx.reply("No active timers for you in this channel.")
            return

        # Otherwise, create a timer
        try:
            seconds, human = parse_duration(duration)
        except ValueError as e:
            await ctx.reply(str(e))
            return

        await ctx.reply(f"⏱️ Timer set for **{human}**. I’ll ping you when it’s done.")

        key = (ctx.channel.id, ctx.author.id)
        task = asyncio.create_task(
            self._sleep_and_notify(
                channel=ctx.channel,
                mention=ctx.author.mention,
                seconds=seconds,
                human=human,
                label=label.strip() or None,
                owner_channel_id=ctx.channel.id,
                owner_user_id=ctx.author.id,
            )
        )
        # Register task under the user's key
        self._active_tasks.setdefault(key, set()).add(task)

        # When task finishes, ensure we remove it
        def _cleanup(_t: asyncio.Task):
            task_set = self._active_tasks.get(key)
            if task_set:
                task_set.discard(_t)
                if not task_set:
                    self._active_tasks.pop(key, None)

        task.add_done_callback(_cleanup)


async def setup(bot: commands.Bot):
    await bot.add_cog(TimerCog(bot))
