import ast
import json
import requests
from discord.ext import commands
from discord import Message, Embed

class Postman:
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.format_message = "Usage: <request_type> <endpoint> <param:param_value> (<auth:bearer-token> optional). Please wrap key value pairs in quotes. accepted request types: put, post, get, delete"

    def _parse_value(self, val):
        if val == 'null': return None
        if val == 'true': return True
        if val == 'false': return False
        try:
            return json.loads(val)
        except:
            try:
                return ast.literal_eval(val)
            except:
                return val

    def _make_request(self, req_type: str, endpoint: str, *args: list[str]):
        payload = {}
        headers = {}
        for argument in args:
            key_val = argument.split(':', 1)
            if len(key_val) != 2:
                return ('error', self.format_message)
            if key_val[0] == 'auth':
                headers['Authorization'] = f'Bearer {key_val[1]}'
            else:
                payload[key_val[0]] = self._parse_value(key_val[1])

        try:
            match req_type.lower():
                case "post":
                    response = requests.post(url=endpoint, json=payload, headers=headers)
                case "get":
                    response = requests.get(url=endpoint, params=payload, headers=headers)
                case "put":
                    response = requests.put(url=endpoint, json=payload, headers=headers)
                case "delete":
                    response = requests.delete(url=endpoint, headers=headers)
                case _:
                    return ('error', self.format_message)
        except Exception as e:
            return ('error', f"Request failed: {str(e)}")

        if not (200 <= response.status_code < 300):
            return ('error', f"Failed with status code {response.status_code}:\n{response.text}")

        try:
            return ('success', json.dumps(response.json(), indent=2))
        except:
            return ('success', response.text)

    async def handle_postman_command(self, message: Message, req_type: str, endpoint: str, *args: str):
        status, response = self._make_request(req_type, endpoint, *args)
        await self._send_response_message(message, status, response)

    async def _send_response_message(self, message: Message, status: str, content: str):
        if status == 'error':
            embed = Embed(title="API Request Failed", description=content, color=0xFF0000)
            await message.reply(embed=embed)
        else:
            try:
                json.loads(content)
                await message.reply(embed=Embed(title="API Response", description=f"```json\n{content}\n```", color=0x00FF00))
            except:
                await message.reply(embed=Embed(title="API Response", description=content, color=0x00FF00))

    async def setup(self):
        @commands.command(name="postman", help=self.format_message)
        async def postman_command(ctx: commands.Context, req_type: str, endpoint: str, *args: str):
            if not req_type or not endpoint:
                await ctx.send("Please provide the request type and endpoint.")
                return

            async with ctx.typing():
                status, response = self._make_request(req_type, endpoint, *args)
                await self._send_response_message(ctx.message, status, response)

        self.bot.add_command(postman_command)
        print("Postman feature loaded and command registered.")