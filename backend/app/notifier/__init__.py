import logging

import httpx

from app import config
from app.timeouts import call_with_timeout

log = logging.getLogger(__name__)

TELEGRAM_API = "https://api.telegram.org"


def notify(text: str) -> bool:
    """Send `text` to TELEGRAM_CHAT_ID via the Telegram bot. Returns True if Telegram accepted it.

    Never raises and never blocks long: no keys, no network or any Telegram error -> False,
    and the UI shows the text itself. The token is part of the URL, so errors are logged
    by type only, never with the request URL.
    """
    if not (config.TELEGRAM_BOT_TOKEN and config.TELEGRAM_CHAT_ID):
        log.info("notification not sent (Telegram not configured): %s", text)
        return False
    try:
        # httpx's timeout does not cover the DNS lookup, which can hang without a network.
        r = call_with_timeout(
            lambda: httpx.post(
                f"{TELEGRAM_API}/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage",
                json={"chat_id": config.TELEGRAM_CHAT_ID, "text": text},
                timeout=config.TELEGRAM_TIMEOUT_SEC,
            ),
            config.TELEGRAM_TIMEOUT_SEC * 2,
        )
        ok = r.status_code == 200 and r.json().get("ok") is True
    except (httpx.HTTPError, ValueError, TimeoutError) as e:
        log.warning("Telegram notification failed: %s", type(e).__name__)
        return False
    if not ok:
        log.warning("Telegram rejected the notification: HTTP %s", r.status_code)
    return ok
