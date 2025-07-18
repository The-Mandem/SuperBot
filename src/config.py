import os
from dotenv import load_dotenv
from pathlib import Path
import argparse


class ConfigManager:
    _instance = None
    _initialized = False  # Class-level flag to ensure __init__ logic runs only once

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(ConfigManager, cls).__new__(cls, *args, **kwargs)
        return cls._instance

    def __init__(self):
        if ConfigManager._initialized:
            return

        # Argument parsing
        parser = argparse.ArgumentParser(
            description="Set application environment (dev/prod).",
        )
        group = parser.add_mutually_exclusive_group(
            required=False
        )  # Not required, because we have a default
        group.add_argument(
            "--dev",
            action="store_true",
            help="Run in development mode. This is the default if no environment flag is specified.",
        )
        group.add_argument(
            "--prod", action="store_true", help="Run in production mode."
        )
        args = parser.parse_args()  # Parses command-line arguments

        # Determine app_env and store it as an instance variable
        self._app_env = "dev"  # Default to development
        if args.prod:
            self._app_env = "prod"

        # Store DOTENV_PATH for error messages and clarity
        CURRENT_SCRIPT_DIR = Path(__file__).resolve().parent
        self._dotenv_path = CURRENT_SCRIPT_DIR.parent / ".env"

        # Load .env file
        if self._dotenv_path.exists():
            load_dotenv(dotenv_path=self._dotenv_path, override=True)
            print(f"INFO: Loaded .env file from: {self._dotenv_path}")
        else:
            print(
                f"INFO: .env file not found at the expected parent directory location: {self._dotenv_path}. "
                "Relying on system environment variables or defaults if tokens are not set."
            )

        # Load Discord token and Gemini key based on app_env
        self._discord_token = None

        if self._app_env == "prod":
            self._discord_token = os.getenv("DISCORD_TOKEN_PROD")
            if not self._discord_token:
                raise ValueError(
                    f"ERROR: APP_ENV is 'prod' but DISCORD_TOKEN_PROD is not set. "
                    f"Checked .env at '{self._dotenv_path}' and system environment variables."
                )
            print("INFO: Running in PRODUCTION mode.")
        elif self._app_env == "dev":
            self._discord_token = os.getenv("DISCORD_TOKEN_DEV")
            if not self._discord_token:
                raise ValueError(
                    f"ERROR: APP_ENV is 'dev' (or default) but DISCORD_TOKEN_DEV is not set. "
                    f"Checked .env at '{self._dotenv_path}' and system environment variables."
                )
            print("INFO: Running in DEVELOPMENT mode.")
        else:
            # This case should ideally not be reached if app_env is correctly defaulted or set by args.
            raise ValueError(
                f"ERROR: Invalid APP_ENV value: '{self._app_env}'. Must be 'prod' or 'dev'. "
                f"Checked .env at '{self._dotenv_path}' and system environment variables."
            )

        # Final check for the token
        if not self._discord_token:
            # This state should ideally not be reached if the logic above is correct and tokens are set.
            raise ValueError(
                "CRITICAL: Discord token could not be loaded. Ensure APP_ENV is correctly set ('prod' or 'dev') "
                "and the corresponding token (DISCORD_TOKEN_PROD or DISCORD_TOKEN_DEV) is available."
            )

        # Load Gemini key
        self._gemini_key = os.getenv("GEMINI_KEY")

        if not self._gemini_key:
            raise ValueError(
                f"ERROR: GEMINI_KEY is not set. "
                f"Checked .env at '{self._dotenv_path}' and system environment variables."
            )

        # Load Tester Channel ID
        self._tester_channel_id = None
        tester_channel_id_str = os.getenv("TESTER_CHANNEL_ID")
        if tester_channel_id_str:
            try:
                self._tester_channel_id = int(tester_channel_id_str)
                print(f"INFO: Loaded TESTER_CHANNEL_ID: {self._tester_channel_id}")
            except ValueError:
                print(
                    f"WARNING: TESTER_CHANNEL_ID '{tester_channel_id_str}' is not a valid integer. Ignoring."
                )
        else:
            print(
                "INFO: TESTER_CHANNEL_ID environment variable not set. The ignore_channel_in_prod decorator will not function."
            )

        ConfigManager._initialized = True

    def get_discord_token(self) -> str:
        """Returns the loaded Discord token."""
        if self._discord_token is None:
            # This should not happen if __init__ completed successfully.
            raise RuntimeError(
                "Discord token accessed before initialization or initialization failed."
            )
        return self._discord_token

    def get_app_env(self) -> str:
        """Returns the current application environment ('dev' or 'prod')."""
        if self._app_env is None:
            # This should not happen if __init__ completed successfully.
            raise RuntimeError(
                "App environment accessed before initialization or initialization failed."
            )
        return self._app_env

    def get_gemini_key(self) -> str:
        """Returns the loaded Gemini API key."""
        if self._gemini_key is None:
            raise RuntimeError(
                "Gemini key accessed before initialization or initialization failed."
            )
        return self._gemini_key

    def get_tester_channel_id(self) -> int | None:
        """Returns the loaded tester channel ID or None if not set/invalid."""
        return self._tester_channel_id
