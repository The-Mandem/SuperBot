from discord import Message
from config import ConfigManager
import functools


def ignore_channel_in_prod():
    """
    Decorator to ignore messages in the configured tester channel when the app environment is 'prod'.
    Assumes the decorated function is an async method of a class that takes 'self' and 'message'.
    """

    def decorator(func):
        @functools.wraps(func)
        async def wrapper(self, message: Message, *args, **kwargs):
            config = ConfigManager()  # Get the singleton instance
            tester_channel_id = config.get_tester_channel_id()

            # Only apply the check if the tester channel ID is configured and the environment is prod
            if (
                tester_channel_id is not None
                and message.channel.id == tester_channel_id
                and config.get_app_env() == "prod"
            ):
                # print(f"Ignoring message in tester channel {tester_channel_id} in prod env.") # Optional debug print
                return  # Ignore the message

            # Otherwise, call the original listener method
            await func(self, message, *args, **kwargs)

        return wrapper

    return decorator
