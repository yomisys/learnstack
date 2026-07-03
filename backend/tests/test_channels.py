"""Channel delivery tests: a complete WhatsApp conversation driven through the
simulator (menu → enroll → video lesson → quiz → certificate), SMS media
degradation, and the USSD webhook protocol."""
import os
import tempfile

os.environ.setdefault("LEARNSTACK_DATABASE_URL",
                      "sqlite:///" + os.path.join(tempfile.mkdtemp(), "chan.db"))

from fastapi.testclient import TestClient  # noqa: E402

from app.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import (Curriculum, CurriculumStatus, Lesson, Module,  # noqa: E402
                        Tenant, User, UserRole)
from app.security import hash_password  # noqa: E402

client = TestClient(app)
PHONE = "+2348012345678"


def setup_module():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    tenant = Tenant(slug="chan", name="Channel Academy",
                    branding={"product_name": "Channel Academy"})
    db.add(tenant)
    db.flush()
    db.add(User(tenant_id=tenant.id, email="admin@example.com",
                password_hash=hash_password("adminpass123"),
                role=UserRole.ADMIN.value))
    cur = Curriculum(tenant_id=tenant.id, slug="course-1", title="Field Course",
                     status=CurriculumStatus.PUBLISHED.value)
    db.add(cur)
    db.flush()
    mod = Module(curriculum_id=cur.id, title="Week 1", sort_order=0)
    db.add(mod)
    db.flush()
    db.add(Lesson(module_id=mod.id, title="Watch and learn", sort_order=0, blocks=[
        {"type": "text", "data": {"body": "Welcome to lesson one."}},
        {"type": "video", "data": {"provider": "upload", "url": "/media/chan/intro.mp4",
                                   "caption": "Intro video"}},
    ]))
    db.add(Lesson(module_id=mod.id, title="Quick check", sort_order=1, blocks=[
        {"type": "quiz", "data": {"pass_score": 50, "questions": [
            {"question": "Is video supported?", "options": ["Yes", "No"], "correct": 0},
            {"question": "2+2?", "options": ["3", "4", "5"], "correct": 1},
        ]}},
    ]))
    db.commit()
    db.close()


def login():
    r = client.post("/api/auth/login", params={"tenant": "chan"},
                    json={"email": "admin@example.com", "password": "adminpass123"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def sim(headers, message, channel="whatsapp", address=PHONE):
    r = client.post("/api/channels/simulate", params={"tenant": "chan"}, headers=headers,
                    json={"channel": channel, "address": address, "message": message})
    assert r.status_code == 200, r.text
    return r.json()["replies"]


def test_whatsapp_full_conversation():
    headers = login()

    # channel not configured yet → webhook 404s, simulator still works
    r = client.post("/api/channels/sms/webhook", params={"tenant": "chan"},
                    data={"from": PHONE, "text": "hi"})
    assert r.status_code == 404

    # configure whatsapp with the simulator provider
    r = client.put("/api/channels/config/whatsapp", params={"tenant": "chan"},
                   headers=headers, json={"provider": "simulator"})
    assert r.status_code == 200, r.text

    # greeting → branded course menu
    replies = sim(headers, "hi")
    assert "Channel Academy" in replies[0]["body"]
    assert "1. Field Course" in replies[0]["body"]

    # pick course 1 → enrolled, lesson 1 delivered with a real video message
    replies = sim(headers, "1")
    types = [m["type"] for m in replies]
    assert types[0] == "text" and "enrolled" in replies[0]["body"]
    assert "video" in types, f"expected a video message, got {types}"
    video = next(m for m in replies if m["type"] == "video")
    assert video["url"] == "/media/chan/intro.mp4"
    assert video["caption"] == "Intro video"
    assert "NEXT" in replies[-1]["body"]

    # NEXT → lesson 1 completed, quiz lesson starts with question 1
    replies = sim(headers, "next")
    assert "Question 1/2" in replies[-1]["body"]

    # garbage answer → re-asked
    replies = sim(headers, "banana")
    assert "between 1 and 2" in replies[0]["body"]

    # answer both questions correctly → graded, course complete, certificate
    replies = sim(headers, "1")
    assert "Question 2/2" in replies[-1]["body"]
    replies = sim(headers, "2")
    joined = " ".join(m["body"] for m in replies)
    assert "2/2" in joined
    assert "Congratulations" in joined
    assert "certificate code" in joined.lower()

    # the certificate is real and publicly verifiable
    code = next(word for word in joined.replace("\n", " ").split()
                if len(word) == 16 and word.isalnum() and word.isupper())
    r = client.get(f"/api/learn/certificates/verify/{code}")
    assert r.status_code == 200
    assert r.json()["curriculum_title"] == "Field Course"

    # PROGRESS reflects completion
    replies = sim(headers, "progress")
    assert "2/2" in replies[0]["body"] and "COMPLETED" in replies[0]["body"]


def test_sms_degrades_media_to_link():
    headers = login()
    replies = sim(headers, "hi", channel="sms", address="+2348099999999")
    replies = sim(headers, "1", channel="sms", address="+2348099999999")
    types = [m["type"] for m in replies]
    assert "video" not in types  # SMS cannot carry media messages
    link_lines = [m["body"] for m in replies if "/media/chan/intro.mp4" in m.get("body", "")]
    assert link_lines and "Intro video" in link_lines[0]


def test_ussd_webhook_protocol():
    headers = login()
    r = client.put("/api/channels/config/ussd", params={"tenant": "chan"},
                   headers=headers, json={"provider": "simulator"})
    assert r.status_code == 200

    # first dial: empty text → CON + menu
    r = client.post("/api/channels/ussd", params={"tenant": "chan"},
                    data={"sessionId": "s1", "phoneNumber": "+2348055555555", "text": ""})
    assert r.status_code == 200
    assert r.text.startswith("CON ")
    assert "Field Course" in r.text

    # select course (cumulative text "1") → lesson text, media summarized not linked
    r = client.post("/api/channels/ussd", params={"tenant": "chan"},
                    data={"sessionId": "s1", "phoneNumber": "+2348055555555", "text": "1"})
    assert r.text.startswith("CON ")
    assert "Welcome to lesson one." in r.text
    assert "/media/" not in r.text  # no unusable links on feature phones
    assert "web version" in r.text
    assert len(r.text) <= 490


def test_config_validation():
    headers = login()
    r = client.put("/api/channels/config/whatsapp", params={"tenant": "chan"},
                   headers=headers, json={"provider": "twilio"})
    assert r.status_code == 400  # twilio is not a whatsapp provider here
    r = client.put("/api/channels/config/carrier-pigeon", params={"tenant": "chan"},
                   headers=headers, json={"provider": "simulator"})
    assert r.status_code == 400
