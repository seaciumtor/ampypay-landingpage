# CLAUDE.md

Guidance for working in this repository. The home-directory `~/CLAUDE.md` defines
general static-project conventions; **this file takes precedence** and describes how
*this* project actually works.

## What this is

The **AmpyPay** marketing landing page — a single-page site for an AI-assisted
enterprise payroll-outsourcing platform (a product of eUnite HCM). It is a heavily
animated static page with one piece of backend functionality: a "Request a demo"
form that stores submissions in SQLite and sends notification + confirmation emails.

No build system, no bundler, no package.json at the root. The frontend is plain
HTML/CSS/JS opened directly or served statically. The backend is a single
dependency-free Python file.

## How the frontend works

Everything the visitor sees is `index.html` (~580 lines, semantic markup) styled by
`css/style.css` (~1160 lines) with self-hosted Inter loaded via `css/fonts.css`.
Behaviour lives in `js/main.js`.

**Page sections** (each an anchor target from the nav):
`#top` (hero) → `#why` → `#platform` (exceptions) → `#confidence` →
`#compliance` → `#security` → `#cta` → footer.

**`js/main.js`** is one big IIFE, ordered top-to-bottom as:
1. Feature detection — `reduced` (prefers-reduced-motion), `hasGsap`, `hasST`,
   `hasThree`, `finePointer`. **Everything degrades gracefully**: content is fully
   visible with no JS, and animation only adds hidden/initial states once the
   libraries are confirmed present. Preserve this guard pattern when editing.
2. Lenis smooth scroll + anchor navigation (respects Lenis offset).
3. Preloader → hero intro timeline (`splitWords` masks each word for the reveal).
4. Scroll-driven reveals (`[data-reveal]`, `[data-split]`), counters
   (`[data-count]`), and SVG confidence rings (`.ring-val`), all via ScrollTrigger.
5. Nav scroll state + mobile burger menu.
6. Desktop-only flourishes: custom cursor, magnetic buttons, hero panel tilt
   (all gated on `finePointer && !reduced && hasGsap`).
7. **Three.js scenes** in `initThreeJS()`: a hero particle wave (`#hero-canvas`) and
   a draggable security globe (`#globe-canvas`) with data-center markers, great-circle
   arcs, and HTML provider-logo badges projected from 3D each frame. The globe's
   landmass dots are rasterised from `js/world-land.js` (bundled Natural Earth
   polygons). Three.js is lazy-loaded after the hero image settles if not already present.
8. **Demo modal** — open/close (locks body scroll, destroys/recreates Lenis), a custom
   accessible employees dropdown, client-side validation, and submit with retry/backoff.

**Vendored libraries** (never CDN): `js/vendor/{gsap.min.js, ScrollTrigger.min.js,
lenis.min.js, three.min.js}`.

**Assets**: `assets/images/` (product shots, `.png` + `.webp` pairs),
`assets/logos/`, `assets/misc/` (data-center provider logos + country flags),
`assets/fonts/` (Inter woff2 subsets). The hero tablet shot is perspective-warped
offline by `scripts/perspective_correct.py` (OpenCV) — re-run that script to
regenerate `hero1-corrected.png`, don't hand-edit the output.

### Cache-busting & version stamps
`index.html` links the stylesheet as `css/style.css?v=9` and carries a
`data-version`/comment date stamp on `<body>`. Bump the `?v=` query when CSS changes
ship, and update the date stamp, so cached clients pick up changes.

## How the demo form works (frontend → backend)

`js/main.js` posts JSON to `DEMO_API`, which is `http://localhost:3001/api/demo` on
localhost and `/api/demo` (same origin) in production. Payload:
`{ name, company, email, phone, job_title, employees, _hp }`. `_hp` is a honeypot —
non-empty means a bot, and the server silently returns success without storing.

The server validates (name/company/email required, email regex), rate-limits by
email (rejects a 4th request from the same address within a short window), stores the
row, then fires two emails on background threads: an admin notification and a
customer confirmation. Submissions are viewable at `/admin?token=...`.

## Backends — IMPORTANT, there are three implementations

Only **one** is deployed. Don't assume the others are live.

### 1. `server.py` — the deployed backend ✅
Stdlib-only Python (`http.server` + `sqlite3` + `smtplib`), no pip install. This is
what `Procfile` and the **root `render.yaml`** run (`python3 server.py`). It does
everything on one port: serves the static frontend, handles `POST /api/demo`, and
serves the admin views (`GET /admin?token=`, `GET /admin/data?token=`). DB file
`demo_submissions.db` (gitignored). Config comes from env vars (see `.env.example`):
`PORT`, `SMTP_*`, `NOTIFY_EMAIL`, `ADMIN_TOKEN`, `DB_PATH`. On boot it loads a local
`.env` if present. **Edit this file for any production backend change.**

### 2. `backend/` — an alternate Express implementation ⚠️ (not deployed by root config)
A richer Node/Express server (`backend/server.js` + `backend/db.js`,
`better-sqlite3`) with session auth, bcrypt password, TOTP 2FA (`speakeasy` + QR),
rate limiting, and a protected admin dashboard at `/ap-control`. It has its own
`backend/render.yaml` and `backend/package.json`. Treat this as a separate, more
secure deployment target — it is **not** what the root `render.yaml`/`Procfile`
launches. If the production deployment ever moves to this, update the root configs.
Its DB schema differs slightly (no `job_title`/`employees` columns).

### 3. `api/demo.php` — a PHP proxy
For shared/PHP hosting: forwards `POST /api/demo.php` to the Python server on
`127.0.0.1:3001`. Only relevant if the site is fronted by Apache/PHP.

## Running locally

```bash
./start.sh          # Python backend on :3001 + static frontend on :3000
```
Then open http://localhost:3000. Admin: http://localhost:3001/admin?token=<ADMIN_TOKEN>.
`js/main.js` auto-points the form at `localhost:3001` when on localhost.

To run the backend alone: `python3 server.py` (serves frontend *and* API on `PORT`,
default 3001 — this mirrors production).

For the Express backend: `cd backend && npm install && npm start`.

## Deploying

Render.com, configured by the **root `render.yaml`**: Python runtime, no build step,
`startCommand: python3 server.py`, `PORT=10000`. SMTP/admin secrets are set in the
Render dashboard (`sync: false`). To ship: commit to `main` and Render redeploys.

## Conventions specific to this repo

- **Brand palette**: navy `#0A1F44` / deep navy `#071737`, accent blue `#2563EA`
  (and `#6E96F5` for the hero eyebrow), cream `#FBFBEE`, orange arc accent `#f97316`.
  Email templates hardcode these inline.
- **Responsive breakpoints** in `style.css`: `768px` (tablet/mobile) and `380px`
  (small phones); the globe parallax is desktop-only (`min-width: 961px`).
- **Accessibility & motion**: keep the `prefers-reduced-motion` and feature-detection
  guards intact; all decorative canvases are `aria-hidden`; icon-only buttons have
  `aria-label`.
- **Reference docs**: `design.html` / `design.md` are design-system references;
  the two PDFs are brand guidelines / brochure (not used at runtime).
  `email-to-customer.html` is a standalone email template preview.
- Keep `server.py` dependency-free (stdlib only) — that's deliberate so Render needs
  no build step.
