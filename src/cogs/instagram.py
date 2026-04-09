import re
import asyncio
import discord
from discord.ext import commands
from discord import Message


class InstagramCog(commands.Cog, name="Instagram"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Matches standard IG post/reel/tv URLs, ignoring trailing query params like ?igsh=...
        self.pattern = re.compile(
            r"(?:https?://)?(?:www\.)?instagram\.com/(?:p|reel|tv|reels)/[a-zA-Z0-9_-]+"
        )

    @commands.Cog.listener()
    async def on_message(self, message: Message):
        """Listener for messages, checks for Instagram links and embeds via kkinstagram."""
        if message.author == self.bot.user:
            return

        # Do not process commands
        if message.content.startswith(self.bot.command_prefix):  # type: ignore
            return

        matches = self.pattern.findall(message.content)
        if not matches:
            return

        # Remove duplicates while preserving order
        seen = set()
        unique_matches = [x for x in matches if not (x in seen or seen.add(x))]

        new_links = []
        for match in unique_matches:
            # Ensure it has https:// so Discord embeds it properly
            if not match.startswith("http"):
                match = "https://" + match

            new_link = match.replace("www.instagram.com", "instagram.com").replace(
                "instagram.com", "kkinstagram.com"
            )
            new_links.append(new_link)

        if new_links:
            print(
                f"Instagram Feature: Converted {len(new_links)} links for {message.author.name}"
            )
            reply_content = "\n".join(new_links)

            try:
                # Reply with the new embedded links (without re-pinging the user)
                await message.reply(reply_content, mention_author=False)

                # Try to suppress the original message's embed so we don't have duplicate previews
                # (Requires "Manage Messages" permission for the bot)
                await asyncio.sleep(
                    1
                )  # Small delay to ensure Discord has processed the original embed
                await message.edit(suppress=True)

            except discord.Forbidden:
                # Bot doesn't have Manage Messages permission, leave the original embed alone
                pass
            except discord.NotFound:
                # Message was deleted by the user before we could edit it
                pass
            except Exception as e:
                print(f"Instagram Feature: Error replying or suppressing embed: {e}")


async def setup(bot: commands.Bot):
    await bot.add_cog(InstagramCog(bot))
