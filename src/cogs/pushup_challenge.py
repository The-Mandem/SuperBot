import json
import math
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict

import discord
from discord.ext import commands, tasks
from discord import Embed, Color

# Configuration
EVENT_START = datetime(2026, 2, 7, 0, 1)  # Feb 7th, 12:01 AM, 2026
EVENT_DURATION = timedelta(hours=24)
EVENT_END = EVENT_START + EVENT_DURATION
GOAL_PUSHUPS = 1000
DATA_FILE = Path(__file__).parent.parent / "data" / "pushup_data.json"

# UI Constants
COLOR_PENDING = Color.from_rgb(114, 137, 218)  # Discord Blurple
COLOR_ACTIVE = Color.from_rgb(52, 152, 219)  # Blue
COLOR_SUCCESS = Color.from_rgb(46, 204, 113)  # Green
COLOR_WARNING = Color.from_rgb(230, 126, 34)  # Orange
COLOR_CRITICAL = Color.from_rgb(231, 76, 60)  # Red
COLOR_DARK = Color.from_rgb(44, 47, 51)  # Dark Grey


class PushUpChallengeCog(commands.Cog, name="PushUpChallenge"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.data: Dict = {
            "total_pushups": 0,
            "contributions": {},  # UserID (str) -> Count (int)
            "reminders_sent": {
                "1h_warning": False,
                "start": False,
                "halfway_time": False,
                "1h_left": False,
                "end": False,
            },
        }
        self._ensure_data_dir()
        self._load_data()
        self.event_loop.start()

    def cog_unload(self):
        self.event_loop.cancel()

    # --- Persistence Helpers ---
    def _ensure_data_dir(self):
        if not DATA_FILE.parent.exists():
            DATA_FILE.parent.mkdir(parents=True, exist_ok=True)

    def _load_data(self):
        if DATA_FILE.exists():
            try:
                with open(DATA_FILE, "r") as f:
                    saved_data = json.load(f)
                    self.data.update(saved_data)
            except Exception as e:
                print(f"PushUpChallenge: Error loading data: {e}")
        else:
            self._save_data()

    def _save_data(self):
        try:
            with open(DATA_FILE, "w") as f:
                json.dump(self.data, f, indent=4)
        except Exception as e:
            print(f"PushUpChallenge: Error saving data: {e}")

    # --- Formatting Helpers ---
    def _get_progress_bar(self, current: int, total: int, length: int = 15) -> str:
        percent = min(1.0, current / total) if total > 0 else 0
        filled_length = int(length * percent)

        # Visual styling
        bar_char = "█"
        empty_char = "░"

        bar = bar_char * filled_length + empty_char * (length - filled_length)
        return f"`{bar}` **{int(percent * 100)}%**"

    def _format_time_remaining(self, target_dt: datetime) -> str:
        now = datetime.now()
        if now >= target_dt:
            return "00h 00m"
        diff = target_dt - now
        total_seconds = int(diff.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        return f"{hours}h {minutes}m"

    def _get_required_pace(self) -> str:
        """Calculates push-ups needed per hour to finish on time."""
        now = datetime.now()
        if now >= EVENT_END:
            return "0 / hr"
        if now < EVENT_START:
            hours_total = EVENT_DURATION.total_seconds() / 3600
            return f"{math.ceil(GOAL_PUSHUPS / hours_total)} / hr"

        remaining_reps = max(0, GOAL_PUSHUPS - self.data["total_pushups"])
        remaining_seconds = (EVENT_END - now).total_seconds()

        if remaining_seconds <= 0:
            return "N/A"

        remaining_hours = remaining_seconds / 3600
        pace = math.ceil(remaining_reps / remaining_hours)
        return f"{pace} / hr"

    async def _broadcast_message(self, embed: Embed):
        for guild in self.bot.guilds:
            channel = discord.utils.get(guild.text_channels, name="general")
            if not channel:
                channel = discord.utils.get(guild.text_channels, name="announcements")
            if not channel and guild.text_channels:
                channel = guild.text_channels[0]

            if channel:
                try:
                    await channel.send(embed=embed)
                except discord.Forbidden:
                    pass

    # --- Event Loop ---
    @tasks.loop(minutes=1)
    async def event_loop(self):
        now = datetime.now()

        # 1. Pre-Event Warning (1 Hour before)
        if not self.data["reminders_sent"]["1h_warning"]:
            time_until_start = EVENT_START - now
            if timedelta(minutes=0) < time_until_start <= timedelta(hours=1):
                embed = Embed(title="⏳ Preparation Phase", color=COLOR_PENDING)
                embed.description = (
                    "**The 1,000 Push-up Challenge begins in 1 hour.**\n"
                    "Prepare your tracking area."
                )
                embed.add_field(
                    name="Start Time",
                    value=f"`{EVENT_START.strftime('%H:%M')}`",
                    inline=True,
                )
                embed.add_field(
                    name="Target", value=f"`{GOAL_PUSHUPS} Reps`", inline=True
                )
                await self._broadcast_message(embed)
                self.data["reminders_sent"]["1h_warning"] = True
                self._save_data()

        # 2. Event Start
        if not self.data["reminders_sent"]["start"]:
            if now >= EVENT_START:
                embed = Embed(title="🟢 Event Started", color=COLOR_SUCCESS)
                embed.description = (
                    "**The 24-hour timer has begun.**\n"
                    f"Team Goal: **{GOAL_PUSHUPS}** push-ups.\n\n"
                    "Use `!pushups log <amount>` to contribute."
                )
                embed.set_footer(text=f"Ends at {EVENT_END.strftime('%Y-%m-%d %H:%M')}")
                await self._broadcast_message(embed)
                self.data["reminders_sent"]["start"] = True
                self._save_data()

        # 3. Halfway Point
        if (
            EVENT_START <= now < EVENT_END
            and not self.data["reminders_sent"]["halfway_time"]
        ):
            if (now - EVENT_START) >= EVENT_DURATION / 2:
                current = self.data["total_pushups"]
                embed = Embed(title="clock: Halfway Mark", color=COLOR_ACTIVE)
                embed.add_field(
                    name="Current Total", value=f"**{current}**", inline=True
                )
                embed.add_field(
                    name="Remaining",
                    value=f"**{max(0, GOAL_PUSHUPS - current)}**",
                    inline=True,
                )
                embed.add_field(
                    name="Progress",
                    value=self._get_progress_bar(current, GOAL_PUSHUPS),
                    inline=False,
                )
                await self._broadcast_message(embed)
                self.data["reminders_sent"]["halfway_time"] = True
                self._save_data()

        # 4. Final Hour
        if (
            EVENT_START <= now < EVENT_END
            and not self.data["reminders_sent"]["1h_left"]
        ):
            if (EVENT_END - now) <= timedelta(hours=1):
                current = self.data["total_pushups"]
                needed = max(0, GOAL_PUSHUPS - current)

                color = COLOR_CRITICAL if needed > 0 else COLOR_SUCCESS
                title = "🚨 Final Hour" if needed > 0 else "🏁 Final Hour (Goal Met)"

                embed = Embed(title=title, color=color)
                embed.description = (
                    f"**{needed}** push-ups remaining to secure victory."
                )
                embed.add_field(
                    name="Current Pace Needed", value=f"**{needed} / hr**", inline=False
                )
                await self._broadcast_message(embed)
                self.data["reminders_sent"]["1h_left"] = True
                self._save_data()

        # 5. Event End
        if not self.data["reminders_sent"]["end"]:
            if now >= EVENT_END:
                current = self.data["total_pushups"]
                success = current >= GOAL_PUSHUPS

                embed = Embed(
                    title="🏆 Challenge Complete" if success else "❌ Challenge Failed",
                    color=COLOR_SUCCESS if success else COLOR_DARK,
                )

                result_msg = (
                    f"We completed **{current}** out of **{GOAL_PUSHUPS}** push-ups."
                )
                embed.description = f"**Time is up.**\n{result_msg}"
                embed.add_field(
                    name="Final Status",
                    value="SUCCESS" if success else "INCOMPLETE",
                    inline=False,
                )

                # Top contributor shoutout
                if self.data["contributions"]:
                    top_user_id = max(
                        self.data["contributions"], key=self.data["contributions"].get
                    )
                    top_count = self.data["contributions"][top_user_id]
                    embed.add_field(
                        name="MVP",
                        value=f"<@{top_user_id}> ({top_count} reps)",
                        inline=False,
                    )

                await self._broadcast_message(embed)
                self.data["reminders_sent"]["end"] = True
                self._save_data()

    @event_loop.before_loop
    async def before_event_loop(self):
        await self.bot.wait_until_ready()

    # --- Commands ---
    @commands.group(name="pushups", aliases=["pu"], invoke_without_command=True)
    async def pushups_group(self, ctx: commands.Context):
        """Access the Push-up Challenge dashboard."""
        await self.stats_command(ctx)

    @pushups_group.command(name="log")
    async def log_command(self, ctx: commands.Context, amount: int):
        """
        Log contribution to the total.
        Usage: !pushups log 25
        """
        now = datetime.now()

        if now < EVENT_START:
            embed = Embed(title="🚫 Event Not Started", color=COLOR_PENDING)
            embed.description = (
                f"Starts in **{self._format_time_remaining(EVENT_START)}**."
            )
            await ctx.reply(embed=embed)
            return

        if now >= EVENT_END:
            embed = Embed(title="🔒 Event Closed", color=COLOR_DARK)
            embed.description = "The submission window has closed."
            await ctx.reply(embed=embed)
            return

        if amount <= 0:
            await ctx.reply("Value must be positive.")
            return
        if amount > 500:
            await ctx.reply("Please split larger sets into multiple logs (Max 500).")
            return

        user_id = str(ctx.author.id)

        # Update Logic
        self.data["total_pushups"] += amount
        current_user_total = self.data["contributions"].get(user_id, 0) + amount
        self.data["contributions"][user_id] = current_user_total
        self._save_data()

        # Calculate impact
        total = self.data["total_pushups"]
        remaining = max(0, GOAL_PUSHUPS - total)

        embed = Embed(title="✅ Contribution Recorded", color=COLOR_SUCCESS)
        embed.set_author(
            name=ctx.author.display_name, icon_url=ctx.author.display_avatar.url
        )

        embed.add_field(name="Logged", value=f"+{amount}", inline=True)
        embed.add_field(name="Your Total", value=f"{current_user_total}", inline=True)
        embed.add_field(
            name="Team Total", value=f"{total} / {GOAL_PUSHUPS}", inline=True
        )

        # Footer progress bar
        embed.description = self._get_progress_bar(total, GOAL_PUSHUPS, length=20)

        if remaining == 0 and (total - amount) < GOAL_PUSHUPS:
            embed.add_field(
                name="🎉 MILESTONE",
                value="**GOAL REACHED!** Any further reps are bonus.",
                inline=False,
            )

        await ctx.reply(embed=embed)

    @pushups_group.command(name="stats", aliases=["dashboard"])
    async def stats_command(self, ctx: commands.Context):
        """View the main event dashboard and leaderboard."""
        total = self.data["total_pushups"]
        now = datetime.now()

        # Determine State
        if now < EVENT_START:
            state_color = COLOR_PENDING
            time_val = self._format_time_remaining(EVENT_START)
            time_label = "Starts In"
        elif now >= EVENT_END:
            state_color = COLOR_DARK
            time_val = "-"
            time_label = "Status"
        else:
            state_color = COLOR_ACTIVE
            time_val = self._format_time_remaining(EVENT_END)
            time_label = "Time Remaining"

        embed = Embed(title="Push-up Challenge Dashboard", color=state_color)

        # Main Metrics
        embed.add_field(
            name="Team Progress", value=f"**{total}** / {GOAL_PUSHUPS}", inline=True
        )
        embed.add_field(name=time_label, value=f"`{time_val}`", inline=True)

        if now < EVENT_END:
            pace = self._get_required_pace()
            embed.add_field(name="Required Pace", value=f"`{pace}`", inline=True)

        # Visual Bar
        embed.add_field(
            name="Visual",
            value=self._get_progress_bar(total, GOAL_PUSHUPS, length=24),
            inline=False,
        )

        # Leaderboard
        sorted_contributors = sorted(
            self.data["contributions"].items(), key=lambda item: item[1], reverse=True
        )

        if not sorted_contributors:
            lb_text = "*No data recorded yet.*"
        else:
            lines = []
            for i, (uid, count) in enumerate(sorted_contributors[:10], 1):
                user = ctx.guild.get_member(int(uid))
                name = user.display_name if user else f"User_{uid}"

                # Medals
                if i == 1:
                    prefix = "🥇"
                elif i == 2:
                    prefix = "🥈"
                elif i == 3:
                    prefix = "🥉"
                else:
                    prefix = f"**{i}.**"

                lines.append(f"{prefix} **{count}** - {name}")
            lb_text = "\n".join(lines)

        embed.add_field(name="🏆 Leaderboard", value=lb_text, inline=False)
        embed.set_footer(text="Log your reps with: !pushups log <amount>")

        await ctx.reply(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(PushUpChallengeCog(bot))
