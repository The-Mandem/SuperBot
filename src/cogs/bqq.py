from discord.ext import commands
from discord import Message


class BqqCog(commands.Cog, name="NoBqq"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.gif_url = "https://cdn.discordapp.com/attachments/1069778927498829844/1306819801469026344/noooooo.gif?ex=682d4548&is=682bf3c8&hm=896f23173cfa729f5c5806bb11ef822fa91d834ec29724153b50caff22a929cd&"

    @commands.Cog.listener()
    async def on_message(self, message: Message):
        """Handler for 'no bqq' messages."""
        if message.author == self.bot.user:
            return

        if "no bqq" in message.content.lower():
            try:
                await message.channel.send(self.gif_url)
            except Exception as e:
                print(f"BQQ Feature: Error sending GIF response: {e}")


async def setup(bot: commands.Bot):
    await bot.add_cog(BqqCog(bot))
