import aiohttp
from discord.ext import commands
import discord
from datetime import datetime
import pytz


class WeatherCog(commands.Cog, name="Weather"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.api_url = "https://weather-zqic.onrender.com/data"

    @commands.command(name="temp")
    async def get_temperature(self, ctx: commands.Context):
        """Fetch the latest recorded temperature from the weather API."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.api_url) as response:
                    if response.status == 200:
                        data = await response.json()

                        # Check if there's an error in the response
                        if "error" in data:
                            await ctx.send(f"❌ {data['error']}")
                            return

                        # Extract temperature and create response
                        temperature = data.get("temperature")
                        humidity = data.get("humidity")
                        pressure = data.get("pressure")
                        timestamp = data.get("timestamp")

                        if temperature is not None:
                            # Create a nice embed for the response
                            embed = discord.Embed(
                                title="🌡️ Latest Temperature Reading",
                                color=discord.Color.blue(),
                            )
                            embed.add_field(
                                name="Temperature",
                                value=f"{temperature}°C",
                                inline=False,
                            )
                            if humidity is not None:
                                embed.add_field(
                                    name="Humidity", value=f"{humidity}%", inline=True
                                )
                            if pressure is not None:
                                embed.add_field(
                                    name="Pressure",
                                    value=f"{pressure} hPa",
                                    inline=True,
                                )
                            if timestamp:
                                # Convert UTC timestamp to Pacific Time
                                try:
                                    # Parse ISO format timestamp
                                    utc_time = datetime.fromisoformat(
                                        timestamp.replace("Z", "+00:00")
                                    )
                                    # Convert to UTC timezone aware if not already
                                    if utc_time.tzinfo is None:
                                        utc_time = pytz.UTC.localize(utc_time)
                                    # Convert to Pacific Time
                                    pt_tz = pytz.timezone("America/Los_Angeles")
                                    pt_time = utc_time.astimezone(pt_tz)
                                    pt_formatted = pt_time.strftime(
                                        "%Y-%m-%d %I:%M:%S %p %Z"
                                    )
                                    embed.set_footer(
                                        text=f"Recorded at: {pt_formatted}"
                                    )
                                except Exception as e:
                                    print(f"Timestamp conversion error: {e}")
                                    embed.set_footer(text=f"Recorded at: {timestamp}")

                            await ctx.send(embed=embed)
                        else:
                            await ctx.send("❌ Temperature data not available")
                    else:
                        await ctx.send(
                            f"❌ Failed to fetch data (Status: {response.status})"
                        )
        except aiohttp.ClientError as e:
            await ctx.send(f"❌ Network error: {str(e)}")
        except Exception as e:
            await ctx.send(f"❌ Error: {str(e)}")


async def setup(bot: commands.Bot):
    await bot.add_cog(WeatherCog(bot))
