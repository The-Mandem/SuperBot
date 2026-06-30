from urllib.parse import unquote

import asyncpg

from config.manager import ConfigManager


def parse_pooler_dsn(dsn: str) -> dict:
    """Parse a Postgres URI, handling @ characters in the password."""
    dsn = dsn.strip()
    for prefix in ("postgresql://", "postgres://"):
        if dsn.startswith(prefix):
            dsn = dsn[len(prefix) :]
            break
    else:
        raise ValueError("SUPABASE_URL must be a postgresql:// connection string")

    if "@" not in dsn:
        raise ValueError("Invalid SUPABASE_URL: missing host")

    userinfo, location = dsn.rsplit("@", 1)
    if ":" not in userinfo:
        raise ValueError("Invalid SUPABASE_URL: missing password")

    user, password = userinfo.split(":", 1)

    if "/" in location:
        hostport, database = location.split("/", 1)
        database = unquote(database.split("?")[0]) or "postgres"
    else:
        hostport, database = location, "postgres"

    if ":" in hostport:
        host, port_str = hostport.rsplit(":", 1)
        port = int(port_str)
    else:
        host, port = hostport, 5432

    return {
        "user": unquote(user),
        "password": unquote(password),
        "host": host,
        "port": port,
        "database": database,
    }


class GifService:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(GifService, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self.config = ConfigManager()
        self._pool: asyncpg.Pool | None = None
        self._initialized = True

    async def _get_pool(self) -> asyncpg.Pool:
        if self._pool is not None:
            return self._pool

        supabase_url = self.config.get_supabase_url()
        if not supabase_url:
            raise RuntimeError(
                "SUPABASE_URL is not configured. Set it in your .env file."
            )

        conn_params = parse_pooler_dsn(supabase_url)
        self._pool = await asyncpg.create_pool(
            **conn_params,
            ssl="require",
            statement_cache_size=0,
            min_size=1,
            max_size=5,
        )
        return self._pool

    async def close(self):
        if self._pool is not None:
            await self._pool.close()
            self._pool = None

    async def store_gif(
        self, trigger_word: str, gif_url: str, creator_username: str
    ) -> None:
        pool = await self._get_pool()
        normalized_trigger = trigger_word.lower()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO gifs (trigger_word, gif_url, creator_username)
                VALUES ($1, $2, $3)
                ON CONFLICT (trigger_word) DO UPDATE
                SET gif_url = EXCLUDED.gif_url,
                    creator_username = EXCLUDED.creator_username,
                    updated_at = NOW()
                """,
                normalized_trigger,
                gif_url,
                creator_username,
            )

    async def get_gifs_for_triggers(self, trigger_words: list[str]) -> dict[str, str]:
        if not trigger_words:
            return {}

        normalized = list({word.lower() for word in trigger_words})
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT trigger_word, gif_url
                FROM gifs
                WHERE trigger_word = ANY($1::text[])
                """,
                normalized,
            )

        return {row["trigger_word"]: row["gif_url"] for row in rows}

    async def list_triggers(self) -> list[str]:
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT trigger_word FROM gifs ORDER BY trigger_word"
            )
        return [row["trigger_word"] for row in rows]
