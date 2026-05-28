# VOIDD Hire — Product Requirements Document

## Problem statement (verbatim from user)
Premium recruitment operations platform called **VOIDD Hire**. Editorial, premium, corporate-modern,
inspired by Michael Page, Randstad, Deel, Stripe editorial layouts. NOT a public job board —
candidates and companies submit operational forms; admin manages everything via dashboard, with
CRM, invoice generation and analytics. Tech stack: Flask + HTML/CSS/Vanilla JS + Postgres/Supabase.

## User personas
- **Candidate**: Submits profile, skills, salary expectation, resume.
- **Company / HR**: Submits hiring brief with role, budget, urgency, timeline.
- **Visitor**: Browses Home, About, Contact pages; may use the contact form.
- **Admin (internal)**: Single seeded operator. Manages candidate pipeline, company briefs,
  CRM notes, placements, invoices and dashboard analytics.

## Architecture (deployed)
- Single Flask application (`/app/backend/app.py`) serves both HTML templates and `/api/*` JSON.
- FastAPI ASGI wrapper (`server.py`) mounts Flask via `a2wsgi.WSGIMiddleware` so uvicorn on port
  8001 handles all API requests as required by Emergent ingress.
- A second process (driven by `yarn start` → `/root/.venv/bin/python3 /app/backend/app.py`) runs
  the same Flask app on port 3000 to serve HTML pages.
- Database: SQLite (`/app/backend/voidd_hire.db`) via SQLAlchemy. Drop-in swap to Supabase Postgres
  by setting `DATABASE_URL` to the pooler connection string.
- Object storage for resume uploads: **Emergent Object Storage**.
- Auth: JWT (HS256, 24h) with bcrypt-hashed admin seeded from env vars.

## Pages implemented
1. `/` — Home (editorial hero, how-it-works, split CTA, quote, CTA band)
2. `/candidate` — Candidate submission form with resume upload
3. `/company` — Hiring brief form
4. `/about` — About + Terms + Privacy
5. `/contact` — Contact form + direct contacts
6. `/login` — Admin login
7. `/admin` — Admin dashboard (KPIs, candidates, companies, placements, invoices, messages)

## Admin dashboard features (implemented)
- KPI grid: candidates, companies, shortlisted, placements, paid revenue, pending revenue
- Submission trend bar chart (vanilla SVG/CSS)
- Candidates by status visual breakdown
- Candidate management with search/status/shortlist filters, detail drawer, status update,
  shortlist toggle, delete, in-app resume viewer (signed download)
- Company management with search, status update, CRM notes
- CRM interaction log (note / call / email / meeting) per entity
- Placements tracker
- Invoice generator with GST split, status update, PDF download (ReportLab)
- Contact messages inbox

## What's been implemented (2026-02 first ship)
- Public website (5 pages) with premium editorial design
- Admin authentication (JWT) with seeded admin
- Candidate & company forms with full server-side validation
- Resume upload via Emergent Object Storage
- Full admin dashboard with CRM, analytics, invoices
- PDF invoice generation with GST structure

## Feature additions (2026-02 iteration 2)
- **Rule-based candidate ↔ role matching** (`/api/admin/companies/<id>/matches`) — 0–100 score combining skills overlap (50pts), experience alignment (20pts), location fit (15pts), salary fit (15pts). Returns per-dimension breakdown and human-readable reasons. Surfaced in admin via a "Matches" button on each company row that opens a ranked drawer with score badges, dimension bars, reasons, "View profile" and one-click "Add to shortlist".
- **Real contact info** wired across site footer, /contact sidebar, and invoice PDFs — `hello@voiddhire.com` · `+91 87936 67303` · `Nigdi, Pimpri-Chinchwad, Pune 411033`.

## Backlog / next phase
- P0: Swap to Supabase Postgres once pooler tenant is active (currently SQLite)
- P1: Email-based invoice delivery (Resend / SendGrid integration)
- P1: Automated candidate ↔ role matching score
- P1: Follow-up reminders / scheduled tasks
- P2: Multi-admin roles + activity audit log
- P2: WhatsApp / Twilio notifications
- P2: Public Render deployment via GitHub
- P2: Optional: PDF resume parsing to auto-extract skills

## Test credentials
- Admin: `admin@voiddhire.com` / `Voidd@Admin2026`
