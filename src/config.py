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
        group = parser.add_mutually_exclusive_group(required=False) # Not required, because we have a default
        group.add_argument(
            '--dev',
            action='store_true',
            help="Run in development mode. This is the default if no environment flag is specified."
        )
        group.add_argument(
            '--prod',
            action='store_true',
            help="Run in production mode."
        )
        args = parser.parse_args() # Parses command-line arguments

        # Determine app_env and store it as an instance variable
        self._app_env = 'dev'  # Default to development
        if args.prod:
            self._app_env = 'prod'

        # Store DOTENV_PATH for error messages and clarity
        CURRENT_SCRIPT_DIR = Path(__file__).resolve().parent
        self._dotenv_path = CURRENT_SCRIPT_DIR.parent / '.env'

        # Load .env file
        if self._dotenv_path.exists():
            load_dotenv(dotenv_path=self._dotenv_path, override=True)
            print(f"INFO: Loaded .env file from: {self._dotenv_path}")
        else:
            print(f"INFO: .env file not found at the expected parent directory location: {self._dotenv_path}. "
                  "Relying on system environment variables or defaults if tokens are not set.")

        # Load Discord token based on app_env and store it as an instance variable
        self._discord_token = None
        if self._app_env == 'prod':
            self._discord_token = os.getenv('DISCORD_TOKEN_PROD')
            if not self._discord_token:
                raise ValueError(
                    f"ERROR: APP_ENV is 'prod' but DISCORD_TOKEN_PROD is not set. "
                    f"Checked .env at '{self._dotenv_path}' and system environment variables."
                )
            print("INFO: Running in PRODUCTION mode.")
        elif self._app_env == 'dev':
            self._discord_token = os.getenv('DISCORD_TOKEN_DEV')
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
            raise ValueError("CRITICAL: Discord token could not be loaded. Ensure APP_ENV is correctly set ('prod' or 'dev') "
                             "and the corresponding token (DISCORD_TOKEN_PROD or DISCORD_TOKEN_DEV) is available.")

        ConfigManager._initialized = True

    def get_discord_token(self) -> str:
        """Returns the loaded Discord token."""
        if self._discord_token is None:
             # This should not happen if __init__ completed successfully.
             raise RuntimeError("Discord token accessed before initialization or initialization failed.")
        return self._discord_token

    def get_app_env(self) -> str:
        """Returns the current application environment ('dev' or 'prod')."""
        if self._app_env is None:
            # This should not happen if __init__ completed successfully.
            raise RuntimeError("App environment accessed before initialization or initialization failed.")
        return self._app_env