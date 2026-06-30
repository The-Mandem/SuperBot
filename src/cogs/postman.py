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
    try:
        ip = ipaddress.ip_address(ip_str)
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
        val = val.strip()
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
                # Be careful with ast.literal_eval on large inputs,
                # but it's okay for short discord messages.
                return ast.literal_eval(val)
            except (ValueError, SyntaxError):
                return val

    async def _make_request(self, req_type: str, endpoint: str, *args: str):
        payload, headers = {}, {}

        for argument in args:
            if ":" not in argument:
                continue

            # Split only on the first colon
            raw_k, raw_v = argument.split(":", 1)
            k, v = raw_k.strip(), raw_v.strip()

            # If user prefixes with h-, treat it as a custom header
            if k.lower().startswith("h-"):
                headers[k[2:]] = v
            elif k.lower() == "auth":
                headers["Authorization"] = f"Bearer {v}"
            else:
                payload[k] = self._parse_value(v)

        parsed = urllib.parse.urlparse(endpoint)
        if parsed.scheme not in ("http", "https") or not parsed.hostname:
            return ("error", None, "Invalid URL. Only public http/https URLs allowed.")

        hostname = parsed.hostname
        try:
            ip_obj = ipaddress.ip_address(hostname)
            if not is_ip_safe(str(ip_obj)):
                return (
                    "error",
                    None,
                    f"Security Violation: Access to private IP {hostname} is forbidden.",
                )
        except ValueError:
            pass

        connector = aiohttp.TCPConnector(resolver=SafeResolver())
        timeout = aiohttp.ClientTimeout(total=10.0)

        try:
            async with aiohttp.ClientSession(
                connector=connector, timeout=timeout
            ) as session:
                method = req_type.upper()

                req_kwargs = {
                    "headers": headers,
                    "allow_redirects": False,
                }  # Block redirects for SSRF safety
                if method in ("GET", "HEAD", "DELETE"):
                    req_kwargs["params"] = payload
                else:
                    req_kwargs["json"] = payload

                async with session.request(method, endpoint, **req_kwargs) as resp:
                    chunk = await resp.content.read(1024 * 1024)

                    encoding = resp.charset or "utf-8"
                    text = chunk.decode(encoding, errors="replace")

                    if not (200 <= resp.status < 300):
                        return (
                            "error",
                            resp.status,
                            f"Server returned status {resp.status}:\n{text[:500]}",
                        )

                    try:
                        # Prettify JSON if applicable
                        return (
                            "success",
                            resp.status,
                            json.dumps(json.loads(text), indent=2),
                        )
                    except (json.JSONDecodeError, TypeError):
                        return ("success", resp.status, text)

        except ValueError as e:
            return ("error", None, f"Security Block: {str(e)}")
        except aiohttp.ClientError as e:
            return ("error", None, f"Network Error: {str(e)}")
        except asyncio.TimeoutError:
            return ("error", None, "Request timed out after 10 seconds.")
        except Exception as e:
            return ("error", None, f"Request Failed: {str(e)}")

    async def _send_response_message(
        self, ctx, status: str, status_code: int, content: str
    ):
        color = 0x00FF00 if status == "success" else 0xFF0000
        title = (
            f"API Response [{status_code}]" if status_code else "Request Blocked/Failed"
        )

        content = content.replace("```", "` ` `")

        truncated = content[:3800] + ("\n...[truncated]" if len(content) > 3800 else "")
        lang = (
            "json" if (content.startswith("{") or content.startswith("[")) else "text"
        )
        desc = f"```{lang}\n{truncated}\n```"

        embed = Embed(title=title, description=desc, color=color)
        await ctx.reply(embed=embed)

    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.command(name="postman")
    async def postman_command(
        self, ctx: commands.Context, req_type: str, endpoint: str, *args: str
    ):
        valid_methods = ("get", "post", "put", "delete", "patch", "head", "options")
        if req_type.lower() not in valid_methods:
            await ctx.reply(
                f"Usage: `!postman <{'|'.join(valid_methods)}> <url> [key:val] [h-header:val] ...`"
            )
            return

        async with ctx.typing():
            status, status_code, response = await self._make_request(
                req_type, endpoint, *args
            )
            await self._send_response_message(ctx, status, status_code, response)


async def setup(bot: commands.Bot):
    await bot.add_cog(PostmanCog(bot))
