"""Messaging channel endpoints: per-tenant config, provider webhooks
(WhatsApp / SMS / USSD), a built-in simulator, and drip reminders.

Webhook URLs carry the tenant slug: https://api.example.com/api/channels/
whatsapp/webhook?tenant=acme — one URL per tenant per provider console.
"""
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.channels import providers
from app.channels.engine import CAPS, handle_inbound
from app.database import get_db
from app.deps import check_tenant_access, get_tenant, require_author
from app.models import Channel, ChannelConfig, Conversation, Enrollment, Tenant, User

router = APIRouter(prefix="/api/channels", tags=["channels"])

PROVIDERS_BY_CHANNEL = {
    "whatsapp": {"meta", "simulator"},
    "sms": {"africastalking", "twilio", "simulator"},
    "ussd": {"africastalking", "simulator"},
}


def _config(db: Session, tenant: Tenant, channel: str) -> ChannelConfig | None:
    return (db.query(ChannelConfig)
            .filter(ChannelConfig.tenant_id == tenant.id,
                    ChannelConfig.channel == channel).first())


def _active_config(db: Session, tenant: Tenant, channel: str) -> ChannelConfig:
    cfg = _config(db, tenant, channel)
    if not cfg or not cfg.is_active:
        raise HTTPException(404, f"{channel} channel is not enabled for this tenant")
    return cfg


# ---- admin: configuration ----
class ChannelConfigIn(BaseModel):
    provider: str
    credentials: dict = Field(default_factory=dict)
    is_active: bool = True


@router.get("/config")
def list_configs(tenant: Tenant = Depends(get_tenant),
                 user: User = Depends(require_author), db: Session = Depends(get_db)):
    check_tenant_access(user, tenant)
    configs = {c.channel: c for c in db.query(ChannelConfig)
               .filter(ChannelConfig.tenant_id == tenant.id).all()}
    return [
        {
            "channel": ch.value,
            "provider": configs[ch.value].provider if ch.value in configs else None,
            "is_active": configs[ch.value].is_active if ch.value in configs else False,
            "credentials": configs[ch.value].credentials if ch.value in configs else {},
            "webhook_path": f"/api/channels/{'ussd' if ch.value == 'ussd' else ch.value + '/webhook'}?tenant={tenant.slug}",
        }
        for ch in Channel
    ]


@router.put("/config/{channel}")
def upsert_config(channel: str, body: ChannelConfigIn,
                  tenant: Tenant = Depends(get_tenant),
                  user: User = Depends(require_author), db: Session = Depends(get_db)):
    check_tenant_access(user, tenant)
    if channel not in CAPS:
        raise HTTPException(400, f"Unknown channel '{channel}'")
    if body.provider not in PROVIDERS_BY_CHANNEL[channel]:
        raise HTTPException(400, f"Provider '{body.provider}' not supported for {channel}. "
                                 f"Options: {sorted(PROVIDERS_BY_CHANNEL[channel])}")
    cfg = _config(db, tenant, channel)
    if not cfg:
        cfg = ChannelConfig(tenant_id=tenant.id, channel=channel)
        db.add(cfg)
    cfg.provider = body.provider
    cfg.credentials = body.credentials
    cfg.is_active = body.is_active
    db.commit()
    return {"channel": channel, "provider": cfg.provider, "is_active": cfg.is_active}


# ---- simulator: test any channel conversation without a provider account ----
class SimulateIn(BaseModel):
    channel: str = "whatsapp"
    address: str = "+2348000000001"
    message: str


@router.post("/simulate")
def simulate(body: SimulateIn, tenant: Tenant = Depends(get_tenant),
             user: User = Depends(require_author), db: Session = Depends(get_db)):
    check_tenant_access(user, tenant)
    if body.channel not in CAPS:
        raise HTTPException(400, f"Unknown channel '{body.channel}'")
    replies = handle_inbound(db, tenant, body.channel, body.address, body.message)
    return {"channel": body.channel, "address": body.address, "replies": replies}


# ---- WhatsApp (Meta Cloud API) ----
@router.get("/whatsapp/webhook")
def whatsapp_verify(request: Request, tenant: Tenant = Depends(get_tenant),
                    db: Session = Depends(get_db)):
    """Meta webhook verification handshake."""
    cfg = _active_config(db, tenant, "whatsapp")
    params = request.query_params
    if (params.get("hub.mode") == "subscribe"
            and params.get("hub.verify_token") == cfg.credentials.get("verify_token")):
        return PlainTextResponse(params.get("hub.challenge", ""))
    raise HTTPException(403, "Verification failed")


@router.post("/whatsapp/webhook")
async def whatsapp_webhook(request: Request, tenant: Tenant = Depends(get_tenant),
                           db: Session = Depends(get_db)):
    cfg = _active_config(db, tenant, "whatsapp")
    payload = await request.json()
    try:
        value = payload["entry"][0]["changes"][0]["value"]
        messages = value.get("messages", [])
    except (KeyError, IndexError, TypeError):
        return {"status": "ignored"}
    for message in messages:
        sender = message.get("from", "")
        if message.get("type") == "text":
            text = message.get("text", {}).get("body", "")
        elif message.get("type") == "interactive":
            interactive = message.get("interactive", {})
            text = (interactive.get("button_reply") or interactive.get("list_reply") or {}).get("title", "")
        else:
            text = "MENU"  # unsupported inbound type: reset to something useful
        if sender:
            replies = handle_inbound(db, tenant, "whatsapp", sender, text)
            providers.send_messages(cfg, sender, replies)
    return {"status": "ok"}


# ---- SMS (Africa's Talking or Twilio inbound) ----
@router.post("/sms/webhook")
async def sms_webhook(request: Request, tenant: Tenant = Depends(get_tenant),
                      db: Session = Depends(get_db)):
    cfg = _active_config(db, tenant, "sms")
    form = dict(await request.form())
    sender = form.get("from") or form.get("From") or ""
    text = form.get("text") or form.get("Body") or ""
    if not sender:
        return {"status": "ignored"}
    replies = handle_inbound(db, tenant, "sms", sender, text)
    providers.send_messages(cfg, sender, replies)
    return {"status": "ok"}


# ---- USSD (Africa's Talking session protocol) ----
@router.post("/ussd", response_class=PlainTextResponse)
async def ussd_session(request: Request, tenant: Tenant = Depends(get_tenant),
                       db: Session = Depends(get_db)):
    """Africa's Talking posts sessionId/phoneNumber/text (cumulative '1*2*1');
    the response body must start with CON (continue) or END (terminate)."""
    _active_config(db, tenant, "ussd")
    form = dict(await request.form())
    phone = form.get("phoneNumber", "")
    raw = form.get("text", "")
    latest = raw.split("*")[-1] if raw else ""
    replies = handle_inbound(db, tenant, "ussd", phone, latest)
    body = "\n".join(r["body"] for r in replies if r["type"] == "text")
    if len(body) > 480:  # keep within feature-phone screen budget
        body = body[:477] + "..."
    return PlainTextResponse(f"CON {body}")


# ---- drip reminders (call from cron: hit this daily per tenant) ----
@router.post("/drip/run")
def run_drip(hours_idle: int = 20, tenant: Tenant = Depends(get_tenant),
             user: User = Depends(require_author), db: Session = Depends(get_db)):
    """Nudge every channel learner with an unfinished course who has been
    quiet for `hours_idle`+ hours. MNAIR's daily-lesson cadence as a service."""
    check_tenant_access(user, tenant)
    cutoff = datetime.utcnow() - timedelta(hours=hours_idle)
    stale = (db.query(Conversation)
             .join(Enrollment, Conversation.enrollment_id == Enrollment.id)
             .filter(Conversation.tenant_id == tenant.id,
                     Conversation.updated_at < cutoff,
                     Enrollment.completed_at.is_(None))
             .all())
    sent = 0
    for convo in stale:
        if convo.channel == "ussd":
            continue  # USSD is session-initiated; we cannot push
        cfg = _config(db, tenant, convo.channel)
        if not cfg or not cfg.is_active:
            continue
        title = convo.enrollment.curriculum.title
        providers.send_messages(cfg, convo.address, [
            {"type": "text",
             "body": f"Ready to continue \"{title}\"? Reply NEXT to pick up where you left off."}])
        sent += 1
    return {"reminders_sent": sent, "conversations_checked": len(stale)}
