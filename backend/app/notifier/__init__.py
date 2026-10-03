import logging

log = logging.getLogger(__name__)


def notify(text: str) -> bool:
    """Send a notification to the user. Returns True if it was delivered.

    TODO(F): Telegram bot. Until then nothing is sent and the UI shows the text itself.
    """
    log.info("notification not sent (no notifier): %s", text)
    return False
