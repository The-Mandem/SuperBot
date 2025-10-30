from __future__ import annotations

import asyncio
import re
from datetime import datetime, timedelta
from typing import Optional, Tuple, Dict, Set

import discord
from discord.ext import commands

# Regex for durations like "1h 30m 5s"
DURATION_RE = re.compile(
    r"^\s*(?:(\d+)\s*h)?\s*(?:(\d+)\s*m)?\s*(?:(\d+)\s*s)?\s*$", re.IGNORECASE
)
# Regex for times like "5pm", "17:30", "8:00 AM"
TIME_RE = re.compile(r"^\s*(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\s*$", re.IGNORECASE)


def format_seconds_to_human(seconds: int) -> str:
    """Converts a duration in seconds to a human-readable string like '1 hour 2 minutes'."""
    if seconds <= 0:
        return "0 seconds"
    h = seconds // 3600
    mi = (seconds % 3600) // 60
    s = seconds % 60

    parts = []
    if h:
        parts.append(f"{h} hour" + ("s" if h != 1 else ""))
    if mi:
        parts.append(f"{mi} minute" + ("s" if mi != 1 else ""))
    if s:
        parts.append(f"{s} second" + ("s" if s != 1 else ""))

    return " ".join(parts) if parts else "0 seconds"


def parse_timer_input(raw: str) -> Tuple[int, str]:
    """
    Parses a string for a timer, supporting both durations and specific times.

    Durations: 15m, 2h, 1h30m, 45 (defaults to minutes)
    Times (relative to bot's local time): 5pm, 8:30am, 17:00

    Returns (total_seconds, confirmation_string)
    Raises ValueError if invalid, zero, or too far in the future.
    """
    raw = raw.strip()
    # If user passes only a number, assume minutes
    if raw.isdigit():
        raw = f"{raw}m"

    # First, try to parse as a duration (e.g., 15m, 2h)
    duration_match = DURATION_RE.match(raw)
    if duration_match and any(duration_match.groups()):
        h = int(duration_match.group(1) or 0)
        mi = int(duration_match.group(2) or 0)
        s = int(duration_match.group(3) or 0)

        total = h * 3600 + mi * 60 + s
        human = format_seconds_to_human(total)

    else:
        # If not a duration, try to parse as a specific time (e.g., 5pm, 17:30)
        time_match = TIME_RE.match(raw)
        if not time_match:
            raise ValueError(
                "Invalid format. Use a duration (e.g., `15m`, `2h`) or a time (e.g., `5pm`, `17:30`)."
            )

        h_str, m_str, ampm = time_match.groups()
        h = int(h_str)
        mi = int(m_str or 0)
        ampm = ampm.lower() if ampm else None

        # Validate time parts
        if not (0 <= mi <= 59):
            raise ValueError("Invalid time: minutes must be between 0 and 59.")
        if ampm:  # 12-hour format
            if not (1 <= h <= 12):
                raise ValueError(
                    "Invalid time: 12-hour format hour must be between 1 and 12."
                )
            if ampm == "pm" and h != 12:
                h += 12
            elif ampm == "am" and h == 12:  # Midnight case: 12am is 00:00
                h = 0
        elif not (0 <= h <= 23):  # 24-hour format
            raise ValueError(
                "Invalid time: 24-hour format hour must be between 0 and 23."
            )

        # NOTE: This uses the bot's local system time. Timezones are not handled.
        now = datetime.now()
        target_dt = now.replace(hour=h, minute=mi, second=0, microsecond=0)

        # If the time has already passed today, set it for the next day
        if target_dt <= now:
            target_dt += timedelta(days=1)

        total = int((target_dt - now).total_seconds())

        # *** FIX IS HERE ***
        # Use a portable way to format the time without a leading zero
        time_str = target_dt.strftime("%I:%M %p").lstrip("0")
        human = f"until {time_str}"  # e.g., "until 3:59 AM"

    # Common guardrails for the final calculated duration
    if total <= 0:
        raise ValueError("Duration must be greater than zero.")

    MAX_SECONDS = 24 * 3600  # 24 hours
    if total > MAX_SECONDS:
        if "until" in human:
            raise ValueError("The specified time is more than 24 hours away.")
        else:
            raise ValueError("Max timer duration is 24h. Try a smaller duration.")

    return total, human


class TimerCog(commands.Cog):
    """Simple timers: `!timer 15m [label]` or `!timer 5pm [label]` → replies when done."""

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
                for t in list(task_set):
                    if t.done():
                        task_set.discard(t)
                if not task_set:
                    self._active_tasks.pop(key, None)

            duration_str = format_seconds_to_human(seconds)
            suffix = f" **({label})**" if label else ""
            await channel.send(
                f"{mention} ⏰ Time’s up{suffix}: **{duration_str}** elapsed."
            )
        except asyncio.CancelledError:
            # Timer cancelled due to reload/shutdown or explicit cancel
            pass

    @commands.command(name="timer")
    async def timer_command(
        self, ctx: commands.Context, time_or_duration: str, *, label: str = ""
    ):
        """
        Start or cancel a timer. Pings you when it finishes.
        Usage (Durations):
          !timer 15m
          !timer 1h30m take a break
          !timer 45          # defaults to minutes
        Usage (Specific Times):
          !timer 5pm
          !timer 18:30 dinner time
          !timer 3:59am
        Cancellation:
          !timer cancel      # cancels all your timers in this channel
        """
        # Handle cancellation
        if time_or_duration.lower() in {"cancel", "stop"}:
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
            seconds, human = parse_timer_input(time_or_duration)
        except ValueError as e:
            await ctx.reply(str(e))
            return

        # Smart confirmation message
        if human.startswith("until"):
            time_str = human.split(" ", 1)[1]
            await ctx.reply(f"⏱️ Timer set. I’ll ping you at **{time_str}**.")
        else:
            await ctx.reply(
                f"⏱️ Timer set for **{human}**. I’ll ping you when it’s done."
            )

        key = (ctx.channel.id, ctx.author.id)
        task = asyncio.create_task(
            self._sleep_and_notify(
                channel=ctx.channel,
                mention=ctx.author.mention,
                seconds=seconds,
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
