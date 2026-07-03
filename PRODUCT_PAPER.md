# LearnStack
## White-Label Curriculum Delivery, as a Service

**Product Paper — July 2026**

---

## 1. Executive Summary

LearnStack is a multi-tenant SaaS platform that lets any organization launch a
fully branded online academy in a day — their name, their logo, their colors,
their domain — and deliver any curriculum through it: video, rich text, audio,
documents, embeds, and graded quizzes, with enrollment tracking and verifiable
certificates. Delivery is **multi-channel**: full-fidelity web, WhatsApp with
real media messages, SMS, and USSD for feature phones — one lesson authored
once, delivered everywhere a learner can be reached.

The platform is production-derived, not speculative. It grew out of MNAIR
(Make Nigeria AI Ready), a national AI literacy platform that delivered a
7-day, 175-lesson curriculum in five Nigerian languages and ran a live pilot
across 254 users in 11 Nigerian states. LearnStack generalizes that engine:
where MNAIR delivers one curriculum for one brand, LearnStack delivers any
curriculum for any brand, with each customer isolated inside their own tenant.

The business model is straightforward B2B SaaS: training providers, NGOs,
government programs, and corporate L&D teams pay a monthly platform fee to run
their academy on LearnStack instead of building one or renting a generic LMS
that carries someone else's brand.

---

## 2. The Problem

Organizations that need to teach at scale face a bad set of options:

1. **Build their own platform.** Six months and a development team most
   training businesses, NGOs, and agencies do not have.
2. **Rent a hosted course platform** (Teachable, Thinkific, Kajabi). Fast, but
   the customer's academy lives on someone else's brand and URL structure,
   pricing scales punitively with students, and content is locked in — there
   is no portable export of a full curriculum.
3. **Self-host an open-source LMS** (Moodle, Open edX). Free software,
   expensive reality: server administration, plugin maintenance, and an
   interface learners tolerate rather than enjoy.

The gap is sharpest for the organizations LearnStack grew up around:
African training academies, civic literacy programs, and government
initiatives that need **their own brand** in front of learners and funders,
need **certificates that third parties can verify**, and need **curricula that
move with them** — imported from what they already have, exported when they
leave.

---

## 3. Evidence: The MNAIR Foundation

LearnStack is the productized core of a platform that already worked:

- **175 lessons** across 12 modules, authored once and delivered in English,
  Pidgin, Hausa, Yoruba, and Igbo
- **254-user pilot across 11 Nigerian states** with strong lesson-completion
  engagement
- Government demand signal: NITDA and the NITDA–NYSC digital literacy
  ambassador program actively seeking platform partners (2026)
- NDPA-compliant data handling (consent tracking, retention discipline)

The pilot proved the delivery engine, the quiz/certificate loop, and the
multilingual content model. LearnStack's bet is that dozens of organizations
need exactly this machinery under their own name. The MNAIR curriculum itself
imports into LearnStack with one command and serves as both the reference
implementation and the first flagship tenant.

---

## 4. Product Overview

### 4.1 White-label multi-tenancy

Every customer is a **tenant** with its own branding: product name, tagline,
logo, favicon, primary/secondary colors, footer, and support email. The
learner-facing app fetches branding at boot and themes itself at runtime — one
codebase, unlimited brands. Tenants resolve per request (`X-Tenant` header or
`?tenant=` slug), so mapping a customer's custom domain to their academy is a
one-line reverse-proxy rule. Data isolation is enforced at the API layer on
every route and covered by automated tests.

**Roles:** platform operator (superadmin) → tenant admin → instructor →
learner. Tenant admins manage their own branding, staff, and content without
touching anyone else's.

### 4.2 Author any lesson format

Lessons are ordered lists of typed **content blocks**:

| Block | What it delivers |
|---|---|
| `text` | Rich text / Markdown |
| `video` | YouTube, Vimeo, or direct upload (mp4/webm/mov) |
| `audio` | Podcast-style lessons, language drills |
| `image` | Diagrams, infographics, with captions |
| `file` | PDFs, slide decks, worksheets |
| `embed` | Any external tool via iframe |
| `quiz` | Multiple-choice with pass thresholds, graded server-side |

The Studio (admin console) provides a block editor with drag-ordering, media
upload, and a live learner preview beside the editor. Answer keys never leave
the server; learners get graded results, not the key.

### 4.3 Deliver any curriculum

The content hierarchy is deliberately simple — **curriculum → modules →
lessons → blocks** — because it maps onto everything from a 7-day WhatsApp
literacy program to a university short course. Two properties matter:

- **Portability.** A whole curriculum round-trips as one JSON document
  (`import`/`export` endpoints). Customers arrive with content and can leave
  with it. A YAML importer already migrates MNAIR-format curricula wholesale.
- **Draft/publish lifecycle.** Curricula are invisible to learners until
  published; unpublishing is instant.

### 4.4 Multi-channel delivery: web, WhatsApp, SMS, USSD

The same lesson, authored once, reaches learners wherever they are — this is
the capability MNAIR proved nationally, now available to every tenant:

- **Web**: full fidelity — embedded/uploaded video, audio, images, files,
  interactive quizzes.
- **WhatsApp** (Meta Cloud API): lessons arrive as conversation — text
  messages plus **real video, audio, image, and document messages**, quizzes
  answered by reply, certificates delivered with their verification code.
- **SMS** (Africa's Talking or Twilio): text chunked to segment limits; media
  degrades gracefully to a captioned link.
- **USSD** (Africa's Talking `CON`/`END` sessions): text-only delivery for
  feature phones with no data plan — the same curriculum, no smartphone
  required.

One conversation engine drives all three messaging channels per tenant:
course menu → enroll → lesson delivery → quiz (graded server-side, same
engine as the web) → progress → certificate. Each tenant connects its own
provider credentials (or platform-shared numbers), keeping the white-label
promise on the messaging side. A built-in **conversation simulator** in the
Studio lets a tenant test every flow on every channel before connecting a
provider account. Drip reminders nudge idle learners ("Reply NEXT to
continue") on a cron cadence — MNAIR's 7-day program pattern as a feature.

### 4.5 Learn, prove, verify

Learners self-register inside a tenant, enroll, and progress lesson by lesson.
Quizzes gate lesson completion where authors want them to. When a learner
finishes every lesson, the platform issues a **certificate with a unique
verification code**; anyone — an employer, a funder, a ministry — can check it
on a public verification page, no account required. This closes the loop that
made MNAIR credible to institutional partners.

---

## 5. Architecture and Technology

| Layer | Choice | Why |
|---|---|---|
| API | FastAPI (Python 3.10+) | Same stack as MNAIR; OpenAPI docs for free |
| Data | SQLAlchemy 2 — SQLite for dev, PostgreSQL in production | Zero-infrastructure trials, boring-reliable scale path |
| Auth | JWT + PBKDF2 password hashing | Stateless, standard, no native-dependency headaches |
| Media | Local disk per tenant, one-function swap to S3/GCS | Ship now, scale later without API changes |
| Channels | One conversation engine; Meta Cloud API, Africa's Talking, Twilio adapters | Same lesson blocks render per channel capability |
| Frontend | React + Vite + MUI, runtime-themed per tenant | One deploy serves every brand |
| Packaging | Docker Compose (Postgres + API + nginx frontend) | Single-command production bring-up |

Single database, shared schema, `tenant_id` on every row — the standard
SaaS pattern that keeps operations cheap until a customer is big enough to
justify dedicated infrastructure (at which point the same image deploys
standalone, which is itself a sellable "enterprise isolated" tier).

Test coverage runs the full commercial lifecycle end-to-end: create tenant →
brand it → author content → learner enrolls → passes quiz → certificate
issued → certificate verifies — plus explicit cross-tenant isolation tests.

---

## 6. Target Customers and Use Cases

1. **Training academies and bootcamps** (first paying segment). Tech, trade,
   and professional trainers across Nigeria and West Africa who currently
   teach through WhatsApp groups and PDFs. They get a branded academy,
   structured curricula, and verifiable certificates at a fraction of a
   custom build.
2. **Government and NGO programs.** The NITDA–NYSC ambassador model
   generalizes: each agency or program becomes a tenant with its own identity
   and reporting, on shared national infrastructure. MNAIR is the working
   proof.
3. **Corporate L&D and compliance.** Onboarding and certification for
   distributed workforces; the certificate verification page doubles as an
   audit trail.
4. **Edtech entrepreneurs.** Subject-matter experts who want to sell a
   course under their own brand without becoming platform engineers —
   the segment Teachable serves, minus the brand tax and lock-in.

---

## 7. Competitive Landscape

| | LearnStack | Teachable / Thinkific | Moodle (self-host) | TalentLMS |
|---|---|---|---|---|
| True white-label (customer's brand only) | ✅ core design | Partial, premium tiers | ✅ with effort | Partial |
| Multi-tenant operator model (run many academies) | ✅ | ❌ one brand per account | ❌ one install per org | Limited |
| Curriculum portability (full JSON in/out) | ✅ | ❌ | Partial | ❌ |
| Publicly verifiable certificates | ✅ | Add-on | Plugin | ✅ |
| WhatsApp / SMS / USSD curriculum delivery | ✅ shipped | ❌ | ❌ | ❌ |
| Ops burden on customer | None | None | High | None |
| Low-bandwidth / multilingual heritage | ✅ (MNAIR) | ❌ | Neutral | ❌ |

The defensible position is the combination: **operator-grade multi-tenancy +
content portability + certificate verification**, with an origin story and
feature bias (multilingual, low-bandwidth, WhatsApp/USSD roadmap) matched to
markets the incumbents treat as afterthoughts.

---

## 8. Business Model

Per-tenant subscription, priced on active learners rather than content volume
(authors should never be punished for creating more):

| Tier | Target | Indicative price | Includes |
|---|---|---|---|
| **Starter** | Solo trainers | $29/mo (₦ equivalent, local pricing) | 1 curriculum live, 100 active learners, LearnStack subdomain |
| **Growth** | Academies | $99/mo | Unlimited curricula, 1,000 learners, custom domain, certificate verification |
| **Institution** | Gov/NGO/corporate | $499+/mo | Unlimited learners, SLA, dedicated onboarding, data-residency options |
| **Sovereign** | National programs | Custom | Isolated deployment of the same stack, operator training |

Additional revenue levers, in order of build cost: curriculum-import services
(migrating a customer's existing content — high-touch, high-margin, already
half-automated), certificate volume for institutional verifiers, and, later, a
revenue share on paid-course checkout.

**Unit economics intuition:** the marginal tenant costs storage plus a slice
of one Postgres instance — near-zero. The cost center is onboarding, which the
Studio, seed tooling, and importer are specifically designed to compress.

---

## 9. Roadmap

**Now (shipped):** multi-tenant white-labeling, block-based authoring with
video, curriculum import/export, enrollments, server-side quiz grading,
verifiable certificates, MNAIR importer, Docker deployment, lifecycle test
suite — **and multi-channel delivery: WhatsApp (with media messages), SMS,
and USSD, with a per-channel simulator and drip reminders.** No incumbent
LMS ships this; it is the wedge for the African market.

**Next 90 days — first revenue:**
- Billing integration (Paystack first — Nigerian market — then Stripe)
- S3-compatible media storage and CDN delivery
- Learner analytics per tenant (enrollment funnels, completion, quiz scores,
  per-channel engagement)
- Custom-domain automation (today: one manual proxy rule per domain)
- Hosted cron for drip cadences (today: tenant-triggered endpoint)

**Two quarters — differentiation:**
- Cohorts and scheduled program starts (the MNAIR "7-day program" pattern,
  full version)
- Multi-language curriculum variants as a first-class concept
- WhatsApp interactive buttons/lists for menus and quiz answers
- AI-assisted authoring: draft a lesson's blocks and quiz from a source
  document

**Four quarters — moat:**
- SCORM/xAPI import for corporate migration deals
- Voice/IVR channel for low-literacy audiences
- Marketplace: tenants license curricula to each other, LearnStack takes a cut

---

## 10. Risks and Honest Unknowns

- **Willingness to pay** in the first segment is assumed, not yet proven; the
  90-day plan exists to get five paying tenants and find out.
- **Incumbent response:** Thinkific/Teachable could deepen white-labeling.
  The multi-tenant operator model and channel delivery (WhatsApp/USSD) are the
  hedges — structural features, not toggles.
- **Payments friction** in NGN (FX, chargebacks) argues for Paystack-first and
  annual invoicing for institutions.
- **Single-database blast radius:** acceptable now, mitigated by the
  documented per-customer isolated-deployment path.

---

## 11. Summary

LearnStack turns a proven, nationally piloted curriculum-delivery engine into
infrastructure any organization can rent under its own name. The product is
built and verified end-to-end; the first flagship curriculum (MNAIR) imports
in one command; the near-term work is billing, storage, and five design
partners — not research.

**One line:** *Shopify made everyone a store. LearnStack makes everyone an
academy.*

---

*Appendix — try it in five minutes:* `README.md` covers local setup. Seeded
demo: tenant `demo`, admin `admin@demo.local`, sample curriculum plus the full
MNAIR English curriculum (7 modules, 35 lessons) pre-imported.
