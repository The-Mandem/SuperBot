import re

import discord
from discord.ext import commands

from services.gif_service import GifService


class GifsCog(commands.Cog, name="Gifs"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.gif_service = GifService()

    async def cog_unload(self):
        await self.gif_service.close()

    def _substitute_triggers(self, text: str, replacements: dict[str, str]) -> str:
        result = text
        for trigger_word, gif_url in replacements.items():
            result = re.sub(
                rf"\b{re.escape(trigger_word)}\b",
                gif_url,
                result,
                flags=re.IGNORECASE,
            )
        return result

    @commands.command(name="store")
    async def store_command(self, ctx: commands.Context, name: str, gif_url: str):
        """Store a GIF trigger word and URL in Supabase."""
        trigger_word = name.strip()
        if not trigger_word:
            await ctx.reply("Please provide a trigger word name.")
            return

        try:
            await self.gif_service.store_gif(
                trigger_word=trigger_word,
                gif_url=gif_url,
                creator_username=str(ctx.author),
            )
        except RuntimeError as e:
            await ctx.reply(str(e))
            return
        except Exception as e:
            await ctx.reply(f"Failed to store GIF: {e}")
            return

        await ctx.reply(f"Stored GIF for trigger `{trigger_word.lower()}`.")

    @commands.command(name="triggers", aliases=["gifs"])
    async def list_triggers_command(self, ctx: commands.Context):
        """List all stored GIF trigger words."""
        try:
            triggers = await self.gif_service.list_triggers()
        except RuntimeError as e:
            await ctx.reply(str(e))
            return
        except Exception as e:
            await ctx.reply(f"Failed to load trigger words: {e}")
            return

        if not triggers:
            await ctx.reply(
                "No trigger words stored yet. Use `!store <name> <gif_url>`."
            )
            return

        trigger_list = ", ".join(f"`{word}`" for word in triggers)
        await ctx.reply(f"**{len(triggers)} trigger word(s):** {trigger_list}")

    @commands.command(name="gif")
    async def gif_command(self, ctx: commands.Context, *, content: str):
        """Replace trigger words with stored GIFs, or send GIFs directly."""
        if not content.strip():
            await ctx.reply(
                "Usage: `!gif <trigger words>` or `!gif <trigger words> -- <message text>`"
            )
            return

        reply_to_id = None
        trigger_words: list[str]
        source_text: str | None

        if "--" in content:
            trigger_part, source_text = content.split("--", 1)
            trigger_words = trigger_part.split()
            source_text = source_text.strip()
        elif ctx.message.reference and ctx.message.reference.message_id:
            trigger_words = content.split()
            ref = ctx.message.reference.resolved
            if ref is None:
                ref = await ctx.channel.fetch_message(ctx.message.reference.message_id)
            source_text = ref.content
            reply_to_id = ctx.message.reference.message_id
        else:
            words = content.split()
            try:
                known_gifs = await self.gif_service.get_gifs_for_triggers(words)
            except RuntimeError as e:
                await ctx.reply(str(e))
                return
            except Exception as e:
                await ctx.reply(f"Failed to load GIFs: {e}")
                return

            trigger_words = []
            index = 0
            while index < len(words) and words[index].lower() in known_gifs:
                trigger_words.append(words[index])
                index += 1

            if not trigger_words:
                trigger_words = words

            source_text = " ".join(words[index:]).strip() or None

        if not trigger_words:
            await ctx.reply("Please provide at least one trigger word.")
            return

        try:
            replacements = await self.gif_service.get_gifs_for_triggers(trigger_words)
        except RuntimeError as e:
            await ctx.reply(str(e))
            return
        except Exception as e:
            await ctx.reply(f"Failed to load GIFs: {e}")
            return

        if not replacements:
            await ctx.reply("None of those trigger words have stored GIFs.")
            return

        if source_text is None:
            result = " ".join(
                replacements[word.lower()]
                for word in trigger_words
                if word.lower() in replacements
            )
        else:
            result = self._substitute_triggers(source_text, replacements)

        if not result:
            await ctx.reply("No GIFs to send.")
            return

        try:
            await ctx.message.delete()
        except discord.Forbidden:
            await ctx.reply("I don't have permission to delete your command message.")
            return
        except discord.NotFound:
            pass

        reference = (
            discord.MessageReference(message_id=reply_to_id, channel_id=ctx.channel.id)
            if reply_to_id
            else None
        )
        await ctx.channel.send(result, reference=reference)


async def setup(bot: commands.Bot):
    await bot.add_cog(GifsCog(bot))
