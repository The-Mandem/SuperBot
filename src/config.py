import os
from dotenv import load_dotenv
from pathlib import Path

# Directory containing this config.py file (e.g., /project/src)
# This assumes config.py is in the same directory as your other script files like main.py
CURRENT_SCRIPT_DIR = Path(__file__).resolve().parent

# Path to the .env file, expected in the parent directory of CURRENT_SCRIPT_DIR
# e.g., if config.py is in /project/src/, .env should be in /project/.env
DOTENV_PATH = CURRENT_SCRIPT_DIR.parent / '.env'

# Load the .env file if it exists at the specified path
if DOTENV_PATH.exists():
    load_dotenv(dotenv_path=DOTENV_PATH)
    print(f"INFO: Loaded .env file from: {DOTENV_PATH}")
else:
    # If .env is not in the parent directory, os.getenv() will rely on actual environment variables
    # or pre-existing loaded .env by other means.
    print(f"INFO: .env file not found at the expected parent directory location: {DOTENV_PATH}. "
          "Relying on system environment variables or defaults if tokens are not set.")

# Get the application environment (dev, prod), default to 'dev'
# Set APP_ENV=prod in your .env file or system environment to use production settings
APP_ENV = os.getenv('APP_ENV', 'dev').lower()

DISCORD_TOKEN = None

if APP_ENV == 'prod':
    DISCORD_TOKEN = os.getenv('DISCORD_TOKEN_PROD')
    if not DISCORD_TOKEN:
        raise ValueError(
            f"ERROR: APP_ENV is 'prod' but DISCORD_TOKEN_PROD is not set. "
            f"Checked .env at '{DOTENV_PATH}' and system environment variables."
        )
    print("INFO: Running in PRODUCTION mode.")
elif APP_ENV == 'dev':
    DISCORD_TOKEN = os.getenv('DISCORD_TOKEN_DEV')
    if not DISCORD_TOKEN:
        raise ValueError(
            f"ERROR: APP_ENV is 'dev' (or default) but DISCORD_TOKEN_DEV is not set. "
            f"Checked .env at '{DOTENV_PATH}' and system environment variables."
        )
    print("INFO: Running in DEVELOPMENT mode.")
else:
    raise ValueError(
        f"ERROR: Invalid APP_ENV value: '{APP_ENV}'. Must be 'prod' or 'dev'. "
        f"Checked .env at '{DOTENV_PATH}' and system environment variables."
    )

# Final check, though the logic above should catch missing tokens.
if not DISCORD_TOKEN:
    # This state should ideally not be reached if APP_ENV is valid and the corresponding token is set.
    raise ValueError("CRITICAL: Discord token could not be loaded. Ensure APP_ENV is correctly set ('prod' or 'dev') "
                     "and the corresponding token (DISCORD_TOKEN_PROD or DISCORD_TOKEN_DEV) is available.")
