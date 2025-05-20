import random
from discord.ext import commands
from discord import Message

class NoBqqFeature:
    def __init__(self, bot: commands.Bot):
        self.bot = bot

        # List of GIFs to respond with
        self.gif_url = "https://cdn.discordapp.com/attachments/1069778927498829844/1306819801469026344/noooooo.gif?ex=682d4548&is=682bf3c8&hm=896f23173cfa729f5c5806bb11ef822fa91d834ec29724153b50caff22a929cd&"

    async def setup(self):
        """Registers the listener for 'no bqq' messages."""

        @self.bot.listen("on_message")
        async def no_bqq_listener(message: Message):
            if message.author.bot:
                return

            if "no bqq" in message.content.lower():
                await message.channel.send(random.choice(self.gif_url))
