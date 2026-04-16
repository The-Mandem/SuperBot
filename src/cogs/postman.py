import ast
import json
import asyncio
import urllib.parse
import ipaddress
import socket
import aiohttp
from discord.ext import commands
from discord import Embed


def is_ip_safe(ip_str: str) -> bool:
    """Check if an IP address is public and safe to access."""
    try:
        ip = ipaddress.ip_address(ip_str)
        # Check against all unsafe ranges
        return ip.is_global and not (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
        )
    except ValueError:
        return False


class SafeResolver(aiohttp.abc.AbstractResolver):
    """Blocks SSRF for hostnames (e.g. 'localhost' or 'internal.server')"""

    async def resolve(self, host: str, port: int = 0, family: int = socket.AF_UNSPEC):
        loop = asyncio.get_running_loop()
        try:
            infos = await loop.getaddrinfo(
                host, port, family=family, type=socket.SOCK_STREAM
            )
        except socket.gaierror:
            raise ValueError(f"Could not resolve host: {host}")

        safe_hosts = []
        for family, _type, proto, _canonname, sockaddr in infos:
            ip_str = sockaddr[0]
            if not is_ip_safe(ip_str):
                raise ValueError(
                    f"Security Block: {host} resolves to private IP {ip_str}"
                )

            safe_hosts.append(
                {
                    "hostname": host,
                    "host": ip_str,
                    "port": sockaddr[1],
                    "family": family,
                    "proto": proto,
                    "flags": socket.AI_NUMERICHOST,
                }
            )
        return safe_hosts

    async def close(self):
        pass


class PostmanCog(commands.Cog, name="Postman"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def _parse_value(self, val):
        if val.lower() == "null":
            return None
        if val.lower() == "true":
            return True
        if val.lower() == "false":
            return False
        try:
            return json.loads(val)
        except json.JSONDecodeError:
            try:
                return ast.literal_eval(val)
            except ValueError:
                return val

    async def _make_request(self, req_type: str, endpoint: str, *args: str):
        payload, headers = {}, {}
        for argument in args:
            if ":" not in argument:
                continue
            k, v = argument.split(":", 1)
            if k.lower() == "auth":
                headers["Authorization"] = f"Bearer {v}"
            else:
                payload[k] = self._parse_value(v)

        # 1. Parse URL and validate scheme
        parsed = urllib.parse.urlparse(endpoint)
        if parsed.scheme not in ("http", "https") or not parsed.hostname:
            return ("error", "Invalid URL. Only public http/https URLs allowed.")

        # 2. PRE-CHECK: If the hostname is a literal IP, block it if it's private
        # This fixes the bypass you encountered.
        hostname = parsed.hostname
        try:
            # Check if it's a valid IP string
            ip_obj = ipaddress.ip_address(hostname)
            if not is_ip_safe(str(ip_obj)):
                return (
                    "error",
                    f"Security Violation: Access to private IP {hostname} is forbidden.",
                )
        except ValueError:
            # Not an IP literal, it's a hostname (like google.com).
            # SafeResolver will handle this during connection.
            pass

        # 3. Request setup
        connector = aiohttp.TCPConnector(resolver=SafeResolver())
        timeout = aiohttp.ClientTimeout(total=10.0)

        try:
            async with aiohttp.ClientSession(
                connector=connector, timeout=timeout
            ) as session:
                method = req_type.upper()
                req_kwargs = {
                    "headers": headers,
                    "params" if method == "GET" else "json": payload,
                }

                async with session.request(method, endpoint, **req_kwargs) as resp:
                    # Read max 1MB to prevent RAM exhaustion
                    chunk = await resp.content.read(1024 * 1024)
                    text = chunk.decode("utf-8", errors="replace")

                    if not (200 <= resp.status < 300):
                        return (
                            "error",
                            f"Server returned status {resp.status}:\n{text[:500]}",
                        )

                    try:
                        return ("success", json.dumps(json.loads(text), indent=2))
                    except (json.JSONDecodeError, TypeError):
                        return ("success", text)
        except ValueError as e:
            return ("error", f"Security Block: {str(e)}")
        except Exception as e:
            return ("error", f"Request Failed: {str(e)}")

    async def _send_response_message(self, ctx, status: str, content: str):
        color = 0x00FF00 if status == "success" else 0xFF0000
        title = "API Response" if status == "success" else "Request Blocked/Failed"

        # Truncate for Discord (4096 char limit)
        truncated = content[:3800] + ("..." if len(content) > 3800 else "")

        lang = "json" if (content.startswith("{") or content.startswith("[")) else ""
        desc = f"```{lang}\n{truncated}\n```"

        await ctx.reply(embed=Embed(title=title, description=desc, color=color))

    @commands.command(name="postman")
    async def postman_command(
        self, ctx: commands.Context, req_type: str, endpoint: str, *args: str
    ):
        if req_type.lower() not in ("get", "post", "put", "delete"):
            await ctx.reply(
                "Usage: `!postman <get|post|put|delete> <url> <key:val>...`"
            )
            return

        async with ctx.typing():
            status, response = await self._make_request(req_type, endpoint, *args)
            await self._send_response_message(ctx, status, response)


async def setup(bot: commands.Bot):
    await bot.add_cog(PostmanCog(bot))
