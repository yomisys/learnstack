"""Outbound message delivery per provider.

Webhook handlers call `send_messages(config, to, messages)`. The engine's
message dicts map onto each provider's wire format here. The `simulator`
provider sends nothing — replies are returned to the caller instead (used by
the built-in simulator endpoint and by webhook tests).
"""
import logging

import httpx

from app.config import settings
from app.models import ChannelConfig

log = logging.getLogger("learnstack.channels")

META_GRAPH = "https://graph.facebook.com/v18.0"
AT_SMS_URL = "https://api.africastalking.com/version1/messaging"


def absolute_url(url: str) -> str:
    return url if url.startswith("http") else f"{settings.public_base_url}{url}"


def _whatsapp_payload(to: str, message: dict) -> dict:
    base = {"messaging_product": "whatsapp", "to": to}
    mtype = message["type"]
    if mtype == "text":
        return {**base, "type": "text", "text": {"body": message["body"]}}
    media = {"link": absolute_url(message["url"])}
    if message.get("caption"):
        media["caption"] = message["caption"]
    return {**base, "type": mtype, mtype: media}


def _as_sms_text(message: dict) -> str:
    if message["type"] == "text":
        return message["body"]
    caption = message.get("caption") or message["type"].capitalize()
    return f"{caption}: {absolute_url(message['url'])}"


def send_messages(config: ChannelConfig, to: str, messages: list[dict]) -> None:
    """Deliver engine output through the tenant's configured provider.

    Failures are logged, not raised: a webhook must always 200 quickly or the
    provider will retry/disable it.
    """
    try:
        if config.provider == "simulator":
            return
        if config.provider == "meta":
            _send_meta(config.credentials, to, messages)
        elif config.provider == "africastalking":
            _send_africastalking(config.credentials, to, messages)
        elif config.provider == "twilio":
            _send_twilio(config.credentials, to, messages)
        else:
            log.error("Unknown provider %r for tenant %s", config.provider, config.tenant_id)
    except Exception:
        log.exception("Failed sending %s message(s) to %s via %s",
                      len(messages), to, config.provider)


def _send_meta(creds: dict, to: str, messages: list[dict]) -> None:
    url = f"{META_GRAPH}/{creds['phone_number_id']}/messages"
    headers = {"Authorization": f"Bearer {creds['access_token']}"}
    with httpx.Client(timeout=15) as client:
        for message in messages:
            r = client.post(url, headers=headers, json=_whatsapp_payload(to, message))
            r.raise_for_status()


def _send_africastalking(creds: dict, to: str, messages: list[dict]) -> None:
    body = "\n\n".join(_as_sms_text(m) for m in messages)
    data = {"username": creds["username"], "to": to, "message": body}
    if creds.get("sender_id"):
        data["from"] = creds["sender_id"]
    with httpx.Client(timeout=15) as client:
        r = client.post(AT_SMS_URL, data=data,
                        headers={"apiKey": creds["api_key"], "Accept": "application/json"})
        r.raise_for_status()


def _send_twilio(creds: dict, to: str, messages: list[dict]) -> None:
    sid = creds["account_sid"]
    url = f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"
    with httpx.Client(timeout=15, auth=(sid, creds["auth_token"])) as client:
        for message in messages:
            r = client.post(url, data={
                "From": creds["from_number"], "To": to, "Body": _as_sms_text(message)})
            r.raise_for_status()
