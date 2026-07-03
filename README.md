# LearnStack — White-Label Curriculum Delivery SaaS

Multi-tenant learning platform derived from the MNAIR project. Each tenant gets
a fully branded (white-label) learning portal, a content studio for authoring
**any curriculum** — video, rich text, audio, images, files, embeds, quizzes —
plus enrollments, progress tracking, and verifiable certificates.

## Architecture

```
learnstack/
├── backend/          FastAPI + SQLAlchemy (SQLite by default, Postgres-ready)
│   ├── app/
│   │   ├── models.py        Tenant, User, Curriculum→Module→Lesson(blocks), Enrollment, Certificate, MediaAsset
│   │   ├── channels/
│   │   │   ├── engine.py    channel-agnostic conversation state machine
│   │   │   └── providers.py Meta WhatsApp / Africa's Talking / Twilio senders
│   │   ├── routers/
│   │   │   ├── auth.py      tenant-scoped register/login (JWT)
│   │   │   ├── tenants.py   tenant CRUD + public branding endpoint
│   │   │   ├── content.py   curriculum/module/lesson authoring + JSON import/export
│   │   │   ├── media.py     video/audio/image/file uploads (local disk, S3-swappable)
│   │   │   ├── learning.py  catalog, enroll, lesson player, quiz grading, certificates
│   │   │   └── channels.py  WhatsApp/SMS/USSD webhooks, config, simulator, drip
│   │   └── ...
│   └── scripts/
│       ├── seed.py                 superadmin + demo tenant + sample course
│       └── import_mnair_yaml.py    import MNAIR curriculum YAML into any tenant
└── frontend/         React + Vite + MUI, themed at runtime from tenant branding
```

### Multi-tenancy & white-labeling

- Single database, shared schema; every row carries `tenant_id`.
- Tenant resolved per request from the `X-Tenant` header or `?tenant=slug`.
  In production, map each customer domain to its slug at the reverse proxy
  (one `proxy_set_header X-Tenant acme;` per white-label domain).
- `GET /api/tenants/branding` is public; the frontend fetches it on boot and
  builds its MUI theme (product name, tagline, logo, colors, footer) from it.
- Roles: `superadmin` (platform operator, cross-tenant), `admin` (tenant),
  `instructor` (authoring only), `learner`.

### Content model

Lessons are ordered lists of typed blocks (`text`, `video`, `audio`, `image`,
`file`, `embed`, `quiz`). Video supports YouTube/Vimeo URLs or direct uploads.
Quiz answers are stored server-side only — learner payloads are stripped and
grading happens on the API. Whole curricula round-trip as portable JSON via
`POST /api/content/curricula/import` and `GET .../export`.

## Quick start

### Backend

```bash
cd backend
python -m venv venv          # Python 3.10+
venv\Scripts\pip install -r requirements.txt
venv\Scripts\python -m scripts.seed
venv\Scripts\uvicorn app.main:app --reload --port 8000
```

Seed accounts (change immediately in real use):
- Platform superadmin: `root@learnstack.local` / `superadmin123`
- Demo tenant admin (tenant `demo`): `admin@demo.local` / `demoadmin123`

> If `files.pythonhosted.org` is blocked on your network (it was on the dev
> machine), install via a mirror:
> `pip install -i https://mirrors.aliyun.com/pypi/simple/ -r requirements.txt`

### Frontend

```bash
cd frontend
npm install
npm run dev        # http://localhost:3000 (proxies /api and /media to :8000)
```

Open `http://localhost:3000/?tenant=demo` — the tenant slug is remembered in
localStorage. Sign in as the demo admin and open **Studio** to edit branding
and build curricula.

### Import the MNAIR curriculum

```bash
cd backend
venv\Scripts\python -m scripts.import_mnair_yaml ^
  --root C:\Users\yomis\mnair\curriculum ^
  --tenant demo --slug-prefix mnair --title "Make Nigeria AI Ready" ^
  --language en --publish
```

Omit `--language` to import all five languages as five curricula.

### Tests

```bash
cd backend
venv\Scripts\python -m pytest tests/ -q
```

Covers the full lifecycle (tenant → branding → authoring → enrollment →
quiz → certificate → verification) and tenant isolation.

## Messaging channels (WhatsApp / SMS / USSD)

Every tenant can deliver its curricula conversationally — the MNAIR delivery
model, generalized. One engine drives all channels; lesson blocks render per
channel capability (WhatsApp gets real video/audio/image messages, SMS gets
captioned links, USSD gets text-only for feature phones).

1. Studio → **Messaging channels** (or `PUT /api/channels/config/{channel}`).
   Providers: `meta` (WhatsApp Cloud API), `africastalking` (SMS + USSD),
   `twilio` (SMS), `simulator` (no account needed — for testing).
2. Point the provider webhook at your API with the tenant slug:
   - WhatsApp: `POST /api/channels/whatsapp/webhook?tenant=<slug>` (GET serves
     Meta's hub.challenge verification; set `verify_token` in credentials)
   - SMS: `POST /api/channels/sms/webhook?tenant=<slug>`
   - USSD: `POST /api/channels/ussd?tenant=<slug>` (Africa's Talking CON/END)
3. Test any flow in the Studio's **conversation simulator** before connecting
   a real provider: send "hi", pick a course, watch lessons/quizzes flow.
4. Drip reminders: schedule `POST /api/channels/drip/run?tenant=<slug>` daily
   (cron) to nudge idle learners with "Reply NEXT to continue."

Learner commands on any channel: a course number to enroll, `NEXT`,
`PROGRESS`, `MENU`, `HELP`. Set `LEARNSTACK_PUBLIC_BASE_URL` so media links
in WhatsApp/SMS messages are absolute.

## Onboarding a new white-label customer

1. Log in as superadmin, `POST /api/tenants` with slug/name/branding.
2. `POST /api/tenants/current/admins?tenant=<slug>` to create their admin.
3. The customer signs into `/?tenant=<slug>`, sets branding in Studio, and
   authors or imports their curriculum.
4. Point their domain at the frontend and set `X-Tenant <slug>` at the proxy.

## Production notes

- Set `LEARNSTACK_JWT_SECRET` and `LEARNSTACK_DATABASE_URL` (Postgres) via env.
- Media is stored on local disk under `backend/uploads/<tenant>/`; swap
  `_store()` in `app/routers/media.py` for S3/GCS when scaling out.
- `docker-compose.yml` runs Postgres + API + frontend.
