from google.genai import types
from discord.ext import commands
from discord import Message
from collections import OrderedDict
from services.gemini_service import GeminiService


class GeminiCog(commands.Cog, name="Gemini"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.gemini_service = GeminiService()
        self.conversations: OrderedDict[int, list[types.Content]] = OrderedDict()
        self.MAX_ACTIVE_CONVERSATIONS = 50
        self.MAX_CONVERSATION_HISTORY_MESSAGES = 50

    def _cleanup_old_conversations(self):
        """Removes the oldest conversation histories if exceeding MAX_ACTIVE_CONVERSATIONS."""
        while len(self.conversations) > self.MAX_ACTIVE_CONVERSATIONS:
            self.conversations.popitem(last=False)

    @commands.command(name="ask", aliases=["gemini", "miku"])
    async def gemini_command(self, ctx: commands.Context, *, prompt: str):
        """Talk to the Gemini AI. Reply to the bot's previous messages to continue a conversation."""
        if not prompt:
            await ctx.reply("Please provide a prompt for Gemini!")
            return

        user_current_prompt_text = prompt
        system_instruction = "Please keep your response concise and brief."
        current_conversation_history: list[types.Content] = []

        thread = []
        latest_message = ctx.message

        while True:
            thread.append(
                f"[{latest_message.created_at.strftime('%Y-%m-%d %H:%M:%S')}] "
                f"{latest_message.author}: {latest_message.content}"
            )

            if not latest_message.reference:
                break

            ref = latest_message.reference
            if ref and ref.message_id:
                latest_message = await ctx.channel.fetch_message(ref.message_id)
            else:
                break

        if thread and len(thread) > 0:
            thread_history = "\n".join(reversed(thread))
            print(f"Thread history: {thread_history}")
            user_current_prompt_text = f"This is the thread history that you are taking into context:\n{thread_history}\n\nNow responding to: {user_current_prompt_text}. if it makes sense to reply with the thread in context, do so"

        if ctx.message.reference and ctx.message.reference.resolved:
            replied_message: Message = ctx.message.reference.resolved  # type: ignore
            if replied_message.author == self.bot.user:
                retrieved_history = self.conversations.get(replied_message.id)
                if retrieved_history:
                    current_conversation_history = list(retrieved_history)
                    self.conversations.move_to_end(replied_message.id)

        current_conversation_history.append(
            types.Content(
                role="user",
                parts=[types.Part.from_text(text=user_current_prompt_text)],
            )
        )

        if len(current_conversation_history) > self.MAX_CONVERSATION_HISTORY_MESSAGES:
            current_conversation_history = current_conversation_history[
                -self.MAX_CONVERSATION_HISTORY_MESSAGES :
            ]

        async with ctx.typing():
            raw_ai_response_text = await self.bot.loop.run_in_executor(
                None,
                self.gemini_service.make_gemini_request,
                current_conversation_history,
                system_instruction,
            )

        if not raw_ai_response_text:
            await ctx.reply(
                "Sorry, an unknown error occurred and no response was generated from Gemini."
            )
            return

        is_error_response = raw_ai_response_text.startswith("Sorry,")

        display_text_parts = []
        if not is_error_response and len(raw_ai_response_text) > 2000:
            current_part = ""
            for line in raw_ai_response_text.splitlines(keepends=True):
                if len(current_part) + len(line) > 1980:
                    display_text_parts.append(current_part.strip())
                    current_part = line
                else:
                    current_part += line
            if current_part.strip():
                display_text_parts.append(current_part.strip())
        else:
            display_text_parts.append(raw_ai_response_text)

        sent_discord_messages: list[Message] = []
        for i, text_content_for_part in enumerate(display_text_parts):
            if not text_content_for_part.strip():
                continue

            message_to_send_discord = text_content_for_part

            try:
                msg_obj = await ctx.reply(message_to_send_discord)
                sent_discord_messages.append(msg_obj)
            except Exception as e:
                print(f"Error sending Discord message part: {e}")
                await ctx.reply(f"Error sending part of the response: {e}")

        if sent_discord_messages and not is_error_response:
            final_sent_message_id = sent_discord_messages[-1].id

            history_to_store = list(current_conversation_history)
            history_to_store.append(
                types.Content(
                    role="model",
                    parts=[types.Part.from_text(text=raw_ai_response_text)],
                )
            )

            if len(history_to_store) > self.MAX_CONVERSATION_HISTORY_MESSAGES:
                history_to_store = history_to_store[
                    -self.MAX_CONVERSATION_HISTORY_MESSAGES :
                ]

            self.conversations[final_sent_message_id] = history_to_store
            self._cleanup_old_conversations()


async def setup(bot: commands.Bot):
    await bot.add_cog(GeminiCog(bot))
