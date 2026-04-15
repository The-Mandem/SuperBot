from discord.ext import commands
from discord import Message
from collections import OrderedDict
from services.litellm_service import LiteLLMService
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.chat_history import InMemoryChatMessageHistory


class GeminiCog(commands.Cog, name="Gemini"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.llm_service = LiteLLMService()
        self.conversations: OrderedDict[int, InMemoryChatMessageHistory] = OrderedDict()
        self.MAX_ACTIVE_CONVERSATIONS = 50
        self.MAX_CONVERSATION_HISTORY_MESSAGES = 50

        self.prompt = ChatPromptTemplate.from_messages(
            [
                ("system", "Please keep your response concise and brief."),
                MessagesPlaceholder(variable_name="history"),
                ("human", "{question}"),
            ]
        )

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
        current_history = InMemoryChatMessageHistory()
        cache_loaded = False

        # 1. Check if replying to the bot's known conversation in memory
        if ctx.message.reference and ctx.message.reference.resolved:
            replied_message: Message = ctx.message.reference.resolved  # type: ignore
            if replied_message.author == self.bot.user:
                retrieved_history = self.conversations.get(replied_message.id)
                if retrieved_history:
                    # Shallow copy the message list to branch off seamlessly
                    current_history.messages = list(retrieved_history.messages)
                    self.conversations.move_to_end(replied_message.id)
                    cache_loaded = True

        # 2. If no cache was loaded but there's a reply chain (e.g. bot restarted, or replying to human),
        # dynamically build the history using proper LangChain AI/Human roles.
        if (
            not cache_loaded
            and ctx.message.reference
            and ctx.message.reference.message_id
        ):
            thread_msgs = []
            curr_msg_id = ctx.message.reference.message_id

            # Traverse up the reply chain (limit to 10 to avoid hitting Discord rate limits)
            for _ in range(10):
                if not curr_msg_id:
                    break
                try:
                    curr_msg = await ctx.channel.fetch_message(curr_msg_id)
                    thread_msgs.append(curr_msg)
                    if curr_msg.reference and curr_msg.reference.message_id:
                        curr_msg_id = curr_msg.reference.message_id
                    else:
                        break
                except Exception as e:
                    print(f"GeminiCog: Failed to fetch thread message: {e}")
                    break

            # Add the fetched messages chronologically to LangChain history
            for msg in reversed(thread_msgs):
                if msg.author == self.bot.user:
                    current_history.add_ai_message(msg.content)
                else:
                    # Prefix human messages with their name so the bot knows who said what
                    current_history.add_user_message(
                        f"{msg.author.display_name}: {msg.content}"
                    )

        # Truncate history to save tokens
        if len(current_history.messages) > self.MAX_CONVERSATION_HISTORY_MESSAGES:
            current_history.messages = current_history.messages[
                -self.MAX_CONVERSATION_HISTORY_MESSAGES :
            ]

        # Format the final prompt value to inject into the LLM
        prompt_value = await self.prompt.ainvoke(
            {"history": current_history.messages, "question": user_current_prompt_text}
        )

        warning_msg = None
        async with ctx.typing():
            try:
                # Stream via Native async LangChain invoke
                (
                    raw_ai_response_text,
                    sent_discord_messages,
                ) = await self.llm_service.stream_to_discord(
                    ctx.message, self.llm_service.primary_llm, prompt_value
                )
            except Exception as e:
                print(f"Gemini API Error: {e}")
                warning_msg = await ctx.reply(
                    "⚠️ **Gemini API failed.** Falling back to local `llama3.2` model. This runs locally on the Raspberry Pi and may take a moment..."
                )
                try:
                    # Async local fallback stream invoke
                    (
                        raw_ai_response_text,
                        sent_discord_messages,
                    ) = await self.llm_service.stream_to_discord(
                        ctx.message, self.llm_service.fallback_llm, prompt_value
                    )
                except Exception as fallback_e:
                    print(f"Local Fallback Error: {fallback_e}")
                    raw_ai_response_text = "Sorry, an unknown error occurred and no response was generated from the AI."
                    sent_discord_messages = [await ctx.reply(raw_ai_response_text)]
                finally:
                    if warning_msg:
                        try:
                            await warning_msg.delete()
                        except Exception as delete_e:
                            print(
                                f"Gemini API: Failed to delete warning message: {delete_e}"
                            )

        if not raw_ai_response_text:
            await ctx.reply(
                "Sorry, an unknown error occurred and no response was generated from Gemini."
            )
            return

        is_error_response = raw_ai_response_text.startswith("Sorry,")

        # Update and map memory to the final message ID
        if sent_discord_messages and not is_error_response:
            final_sent_message_id = sent_discord_messages[-1].id

            current_history.add_user_message(user_current_prompt_text)
            current_history.add_ai_message(raw_ai_response_text)

            self.conversations[final_sent_message_id] = current_history
            self._cleanup_old_conversations()


async def setup(bot: commands.Bot):
    await bot.add_cog(GeminiCog(bot))
