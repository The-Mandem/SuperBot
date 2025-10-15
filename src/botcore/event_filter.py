from config.manager import ConfigManager


def should_ignore_event(event_name: str, args: tuple) -> bool:
    """
    Returns True if the event should be ignored (e.g., messages in tester channel when in prod).
    """
    config = ConfigManager()

    if config.get_app_env() != "prod":
        return False

    if event_name.startswith("on_message") or event_name in {
        "on_reaction_add",
        "on_reaction_remove",
        "on_message_edit",
        "on_typing",
    }:
        message = args[0] if args else None
        if message and message.channel.id == config.get_tester_channel_id():
            return True

    return False
