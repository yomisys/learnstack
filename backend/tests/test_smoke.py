"""End-to-end smoke test over the full tenant lifecycle:
create tenant → brand it → author content → learner enrolls → completes
lessons + quiz → certificate issued and verifiable.
Runs on a throwaway SQLite database.
"""
import os
import tempfile

os.environ["LEARNSTACK_DATABASE_URL"] = "sqlite:///" + os.path.join(
    tempfile.mkdtemp(), "test.db")

from fastapi.testclient import TestClient  # noqa: E402

from app.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import User, UserRole  # noqa: E402
from app.security import hash_password  # noqa: E402

client = TestClient(app)


def setup_module():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    db.add(User(tenant_id=None, email="root@test.local",
                password_hash=hash_password("rootpass123"),
                role=UserRole.SUPERADMIN.value, full_name="Root"))
    db.commit()
    db.close()


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def test_full_lifecycle():
    # creating a tenant requires a superadmin token
    r = client.post("/api/tenants", json={"slug": "acme", "name": "Acme Learning"})
    assert r.status_code == 401

    # login is tenant-scoped, so the platform ships with a bootstrap tenant
    # (created by scripts/seed.py); insert one directly here
    from app.models import Tenant
    db = SessionLocal()
    db.add(Tenant(slug="bootstrap", name="Bootstrap"))
    db.commit()
    db.close()

    r = client.post("/api/auth/login", params={"tenant": "bootstrap"},
                    json={"email": "root@test.local", "password": "rootpass123"})
    assert r.status_code == 200, r.text
    root_token = r.json()["access_token"]

    r = client.post("/api/tenants", params={"tenant": "bootstrap"}, headers=auth(root_token), json={
        "slug": "acme", "name": "Acme Learning",
        "branding": {"product_name": "Acme Learning", "primary_color": "#ff5500"}})
    assert r.status_code == 200, r.text

    # -- white-label branding is publicly readable --
    r = client.get("/api/tenants/branding", params={"tenant": "acme"})
    assert r.status_code == 200
    assert r.json()["branding"]["primary_color"] == "#ff5500"
    assert r.json()["branding"]["product_name"] == "Acme Learning"

    # -- provision tenant admin, author a curriculum via bulk import --
    r = client.post("/api/tenants/current/admins", params={
        "tenant": "acme", "email": "admin@acme.test", "password": "adminpass123"},
        headers=auth(root_token))
    assert r.status_code == 200, r.text

    r = client.post("/api/auth/login", params={"tenant": "acme"},
                    json={"email": "admin@acme.test", "password": "adminpass123"})
    admin_token = r.json()["access_token"]

    r = client.post("/api/content/curricula/import", params={"tenant": "acme"},
                    headers=auth(admin_token), json={
        "curriculum": {"slug": "safety-101", "title": "Safety 101",
                       "description": "Workplace safety basics"},
        "modules": [{
            "title": "Module 1", "lessons": [
                {"title": "Intro video", "blocks": [
                    {"type": "text", "data": {"body": "Welcome!"}},
                    {"type": "video", "data": {"provider": "youtube",
                                               "url": "https://youtube.com/watch?v=x"}}]},
                {"title": "Quiz", "blocks": [
                    {"type": "quiz", "data": {"pass_score": 50, "questions": [
                        {"question": "2+2?", "options": ["3", "4"], "correct": 1}]}}]},
            ]}],
    })
    assert r.status_code == 200, r.text
    curriculum_id = r.json()["id"]
    lesson_ids = [l["id"] for m in r.json()["modules"] for l in m["lessons"]]
    assert len(lesson_ids) == 2

    # invalid block type is rejected
    r = client.post(f"/api/content/curricula/{curriculum_id}/modules",
                    params={"tenant": "acme"}, headers=auth(admin_token),
                    json={"title": "M2"})
    module_id = r.json()["id"]
    r = client.post(f"/api/content/modules/{module_id}/lessons",
                    params={"tenant": "acme"}, headers=auth(admin_token),
                    json={"title": "Bad", "blocks": [{"type": "hologram", "data": {}}]})
    assert r.status_code == 422
    client.delete(f"/api/content/modules/{module_id}", params={"tenant": "acme"},
                  headers=auth(admin_token))

    # draft curricula are hidden from the catalog until published
    r = client.get("/api/learn/catalog", params={"tenant": "acme"})
    assert r.json() == []
    r = client.patch(f"/api/content/curricula/{curriculum_id}", params={"tenant": "acme"},
                     headers=auth(admin_token), json={"status": "published"})
    assert r.status_code == 200

    # -- learner signs up, enrolls, learns --
    r = client.post("/api/auth/register", params={"tenant": "acme"}, json={
        "email": "learner@example.com", "password": "learnerpass1", "full_name": "Ada Learner"})
    assert r.status_code == 200, r.text
    learner_token = r.json()["access_token"]

    r = client.post(f"/api/learn/curricula/{curriculum_id}/enroll",
                    params={"tenant": "acme"}, headers=auth(learner_token))
    assert r.status_code == 200, r.text

    # quiz answers are stripped from learner lesson payloads
    r = client.get(f"/api/learn/lessons/{lesson_ids[1]}", params={"tenant": "acme"},
                   headers=auth(learner_token))
    assert r.status_code == 200
    quiz_block = r.json()["blocks"][0]
    assert "correct" not in quiz_block["data"]["questions"][0]

    r = client.post(f"/api/learn/lessons/{lesson_ids[0]}/complete",
                    params={"tenant": "acme"}, headers=auth(learner_token))
    assert r.status_code == 200
    assert r.json()["curriculum_completed"] is False

    r = client.post(f"/api/learn/lessons/{lesson_ids[1]}/quiz", params={"tenant": "acme"},
                    headers=auth(learner_token), json={"block_index": 0, "answers": [1]})
    assert r.status_code == 200
    assert r.json() == {"score": 1, "total": 1, "passed": True, "correct_answers": [1]}

    # -- completing all lessons issues a verifiable certificate --
    r = client.get("/api/learn/certificates", params={"tenant": "acme"},
                   headers=auth(learner_token))
    assert r.status_code == 200
    certs = r.json()
    assert len(certs) == 1
    r = client.get(f"/api/learn/certificates/verify/{certs[0]['code']}",
                   params={"name": "Ada Learner"})
    assert r.status_code == 200
    assert "learner_name" not in r.json()
    assert r.json()["tenant_name"] == "Acme Learning"

    # -- verify requires the right name, not just a valid code --
    r = client.get(f"/api/learn/certificates/verify/{certs[0]['code']}",
                   params={"name": "Wrong Name"})
    assert r.status_code == 404

    # -- and an unknown code 404s identically, so the endpoint can't be
    #    used to distinguish "bad code" from "right code, wrong name" --
    r = client.get("/api/learn/certificates/verify/DEADBEEF00000000",
                   params={"name": "Ada Learner"})
    assert r.status_code == 404
    assert r.json()["detail"] == "Certificate not found or name does not match"

    # -- the owner can download a real PDF of their own certificate --
    r = client.get(f"/api/learn/certificates/{certs[0]['code']}/pdf",
                   params={"tenant": "acme"}, headers=auth(learner_token))
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content.startswith(b"%PDF")
    assert len(r.content) > 1000  # a real rendered certificate, not a stub

    # -- but nobody else can, including another user in the same tenant --
    r = client.get(f"/api/learn/certificates/{certs[0]['code']}/pdf",
                   params={"tenant": "acme"}, headers=auth(admin_token))
    assert r.status_code == 404


def test_tenant_isolation():
    # tenant B admin cannot read tenant A (acme) content
    r = client.post("/api/auth/login", params={"tenant": "bootstrap"},
                    json={"email": "root@test.local", "password": "rootpass123"})
    root_token = r.json()["access_token"]
    client.post("/api/tenants", params={"tenant": "bootstrap"}, headers=auth(root_token),
                json={"slug": "rival", "name": "Rival Corp"})
    client.post("/api/tenants/current/admins", params={
        "tenant": "rival", "email": "admin@rival.test", "password": "rivalpass123"},
        headers=auth(root_token))
    r = client.post("/api/auth/login", params={"tenant": "rival"},
                    json={"email": "admin@rival.test", "password": "rivalpass123"})
    rival_token = r.json()["access_token"]

    # listing acme content with a rival token → 403 wrong tenant
    r = client.get("/api/content/curricula", params={"tenant": "acme"},
                   headers=auth(rival_token))
    assert r.status_code == 403

    # rival's own catalog does not contain acme curricula
    r = client.get("/api/learn/catalog", params={"tenant": "rival"})
    assert r.json() == []


def test_tenant_analytics():
    """Tenant admin reporting: "how many of our people enrolled/finished."
    Builds on the acme tenant state left behind by test_full_lifecycle
    (one learner, one curriculum, one completed enrollment)."""
    r = client.post("/api/auth/login", params={"tenant": "acme"},
                    json={"email": "admin@acme.test", "password": "adminpass123"})
    assert r.status_code == 200, r.text
    admin_token = r.json()["access_token"]

    # -- summary reflects the one learner who enrolled and completed --
    r = client.get("/api/analytics/summary", params={"tenant": "acme"}, headers=auth(admin_token))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total_learners"] == 1
    assert body["total_enrollments"] == 1
    assert body["completed_enrollments"] == 1
    assert body["completion_rate"] == 100.0
    assert len(body["by_curriculum"]) == 1
    assert body["by_curriculum"][0]["curriculum_title"] == "Safety 101"
    assert body["by_curriculum"][0]["enrolled"] == 1
    assert body["by_curriculum"][0]["completed"] == 1

    # -- roster names the actual person and their progress --
    r = client.get("/api/analytics/learners", params={"tenant": "acme"}, headers=auth(admin_token))
    assert r.status_code == 200, r.text
    roster = r.json()
    assert len(roster) == 1
    entry = roster[0]
    assert entry["full_name"] == "Ada Learner"
    assert entry["email"] == "learner@example.com"
    assert entry["curriculum_title"] == "Safety 101"
    assert entry["completed_at"] is not None
    assert entry["lessons_completed"] == 2
    assert entry["lessons_total"] == 2


def test_self_serve_tenant_signup():
    """A group (church/school/business) creates its own organization and
    admin account in one public, unauthenticated call, and can act as an
    admin of that tenant immediately — no superadmin or invite required."""
    r = client.post("/api/tenants/signup", json={
        "slug": "riverside-church", "org_name": "Riverside Church",
        "admin_full_name": "Pastor Grace", "admin_email": "grace@riverside.example.com",
        "admin_password": "riversidepass1",
    })
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["user"]["role"] == "admin"
    assert body["user"]["email"] == "grace@riverside.example.com"
    token = body["access_token"]

    # the returned token works immediately, scoped to the new tenant
    r = client.get("/api/auth/me", params={"tenant": "riverside-church"}, headers=auth(token))
    assert r.status_code == 200
    assert r.json()["role"] == "admin"

    # and can author content — the whole point of "admin"
    r = client.post("/api/content/curricula", params={"tenant": "riverside-church"},
                    headers=auth(token), json={"slug": "welcome", "title": "Welcome Series"})
    assert r.status_code == 200, r.text

    # a second org can't take an already-claimed URL
    r = client.post("/api/tenants/signup", json={
        "slug": "riverside-church", "org_name": "Copycat Church",
        "admin_full_name": "Someone Else", "admin_email": "someone@copycat.example.com",
        "admin_password": "differentpass1",
    })
    assert r.status_code == 409

    # it does NOT grant superadmin or cross-tenant access
    r = client.get("/api/content/curricula", params={"tenant": "acme"}, headers=auth(token))
    assert r.status_code == 403

    # -- a learner cannot see the roster (PII), only admin/superadmin can --
    r = client.post("/api/auth/login", params={"tenant": "acme"},
                    json={"email": "learner@example.com", "password": "learnerpass1"})
    learner_token = r.json()["access_token"]
    r = client.get("/api/analytics/summary", params={"tenant": "acme"}, headers=auth(learner_token))
    assert r.status_code == 403

    # -- a rival tenant admin cannot see acme's learners (tenant isolation) --
    r = client.post("/api/auth/login", params={"tenant": "rival"},
                    json={"email": "admin@rival.test", "password": "rivalpass123"})
    rival_token = r.json()["access_token"]
    r = client.get("/api/analytics/learners", params={"tenant": "acme"}, headers=auth(rival_token))
    assert r.status_code == 403

    r = client.get("/api/analytics/summary", params={"tenant": "rival"}, headers=auth(rival_token))
    assert r.status_code == 200
    assert r.json()["total_learners"] == 0
