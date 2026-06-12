# AmpyPay Landing Page — Design System

Design reference for the AmpyPay marketing site. Documents the visual language, components, and motion system as built, so new sections and pages stay consistent.

---

## 1. Brand Foundation

**Product**: AmpyPay — AI-assisted enterprise payroll operations platform, powered by eUnite HCM.
**Tagline**: *"We handle payroll. You handle growth."*
**Tone**: Enterprise-grade, confident, precise. Serious infrastructure product — not playful fintech.

Source of truth for brand assets: `AmpyPay Brand Guidelines.pdf` (repo root). Logos live in `assets/logos/` (`logo.svg`, `logo-white.svg`, `icon.svg`, `icon-1.svg` favicon).

---

## 2. Color

Defined as CSS custom properties in `css/style.css` `:root`. Never hardcode colors outside the token set.

### Core palette

| Token | Value | Use |
|---|---|---|
| `--navy` | `#0A1F44` | Primary background, dark sections, headings on light |
| `--navy-deep` | `#071737` | Deeper section variant (compliance, CTA, footer, mobile menu, modal) |
| `--blue` | `#2563EA` | Electric Blue — the accent. CTAs, eyebrows, icons, links, rings, particles |
| `--cream` | `#FBFBEE` | Text on dark, light-section warmth |
| `--ink` | `#0A1F44` | Body text on light sections (same as navy) |

### Semantic / status colors

| Token | Value | Meaning |
|---|---|---|
| `--red` | `#E5484D` | Blockers — must resolve |
| `--amber` | `#E89B0C` | Warnings — review |
| `--purple` | `#7C6AEF` | AI-detected anomalies, AI sparkle `✦` |
| `--green` | `#22C55E` | Confidence score ring, positive/health |

Status colors are always paired with a label or dot, never color alone (`.dot-red`, `.dot-amber`, `.dot-purple`).

### Supporting tints

- `--blue-soft` `rgba(37,99,234,0.14)` — icon chip backgrounds.
- `--line-light` `rgba(251,251,238,0.12)` / `--line-dark` `rgba(10,31,68,0.12)` — hairline borders on dark/light sections respectively.
- `#6E96F5` — lightened blue for eyebrows and numbering on dark backgrounds (raw blue lacks contrast on navy).
- `#1DE2A7` (live) / `#6BA9FF` (ready) — glowing status dots in the CTA.
- Light section background is `#f7f9fa` (`.section-cream`), not pure white; cards within it are `#fff`.

### Section background rhythm

The page alternates dark/light to pace the scroll:

```
Hero            navy-deep → navy gradient
Why AmpyPay     light (#f7f9fa)
Exceptions      navy
Confidence      light (#f7f9fa) — with a navy visual card inset
Compliance      navy-deep
Security        navy
CTA             navy-deep + radial blue glow
Footer          navy-deep
```

Dark sections use `-light` modifier classes (`.h2-light`, `.lead-light`, `.eyebrow-light`, `.footnote-light`).

---

## 3. Typography

**Family**: Inter (variable, weights 300–900), self-hosted woff2 with latin + latin-ext subsets (`assets/fonts/`), `font-display: swap`, preloaded in `<head>`. Fallback: `-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif`.

### Scale

| Role | Spec |
|---|---|
| Hero title | `clamp(2.7rem, 6vw, 5.4rem)`, weight 800, line-height 1.02, letter-spacing −0.035em |
| Section heading `.h2` | `clamp(2.1rem, 4.6vw, 3.6rem)`, weight 800, line-height 1.06, letter-spacing −0.025em, `max-width: 16ch` |
| CTA title | `clamp(2.6rem, 6.4vw, 5.6rem)`, weight 900 |
| Lead paragraph `.lead` | `clamp(1rem, 1.4vw, 1.15rem)`, `max-width: 54ch`, 72%-opacity ink/cream |
| Eyebrow `.eyebrow` | 0.78rem, weight 600, uppercase, letter-spacing 0.18em, blue, with a 34px line dash before |
| Body / card copy | 0.9–1.08rem, 60–72% opacity of section foreground |
| Footnote `.section-footnote` | 0.98rem, weight 600, 3px blue left border |

### Rules

- Headlines are tight (negative tracking, line-height ≈ 1) and heavy (800–900). Body stays at 400–600.
- Reduced-opacity foreground color (not gray hex values) creates text hierarchy: 100% → 72% → 60% → 55%.
- `font-variant-numeric: tabular-nums` on all animated/aligned numbers (counters, stats, preloader).
- Accent words in headlines get `color: var(--blue)` via `.accent` (e.g. "Global Payroll").

### Recurring patterns

- **Eyebrow → H2 → Lead** opens every section, in that order.
- **Numbered list rows** (`01`–`05` in blue mono-style caps) for feature and compliance lists.
- **Footnote bar** (blue left border) closes sections with a summarizing claim.

---

## 4. Layout & Spacing

- **Container**: `min(1200px, 100% − 48px)`, centered. Nav is slightly wider at 1280px.
- **Section padding**: `130px 0 110px` desktop → `90px 0 80px` mobile (≤560px).
- **Grids**: two-column CSS Grid with asymmetric ratios (`1.05fr/0.95fr`, `0.9fr/1.1fr`) and 64–80px gaps; collapse to single column at 960px.
- **Radius scale**: `--radius` 20px for cards · 999px for buttons/pills/chips · 10–16px for inputs, badges, icon chips · 28px for large visual panels.
- **Breakpoints**: 1080px (gap tightening) · **960px** (main layout collapse, burger nav) · **560px** (compact mobile, compact hero fitting one fold) · 380px (smallest-type adjustments). Desktop-only enhancements gate at `min-width: 961px`.
- **Nav height**: `--nav-h: 76px`, fixed; gains blur + translucent navy background after 24px scroll.

### Product screenshots

Screenshots are the visual backbone — every section showcases real UI:

- **Oversized + clipped**: hero shot is 130% width bleeding off the right edge; exceptions visual is 114% wide.
- **Layered collages**: 2–3 overlapping shots with `drop-shadow`, staggered z-index, negative margins (exceptions, compliance). Compliance layers get differential parallax on desktop.
- **Glow behind visuals**: radial `rgba(37,99,234,…)` gradients with `blur(48px)` sit behind layered shots.
- **Floating chips**: pill-shaped glassmorphic callouts (`backdrop-filter: blur(12px)`, translucent navy, hairline border, big soft shadow) anchored around the hero shot, with idle bob animation.
- WebP with `<picture>`/`srcset` where available, `loading="lazy"` for everything below the fold, explicit `width`/`height` to prevent layout shift, `fetchpriority="high"` on the hero shot.

---

## 5. Components

### Buttons
- `.btn` — pill (999px), weight 600, 0.3s transitions. Primary: blue fill, darkens to `#1d52cc` on hover. Ghost: 28%-cream border, brightens on hover. Sizes: `-sm` (nav), default, `-lg` (CTA).
- All major CTAs carry `data-magnetic` (cursor-follow effect) and `data-demo` (opens the demo modal).

### Cards
- **Light-section cards** (`.conf-card`): white, hairline dark border, 18px radius, hover lifts −6px with blue-tinted border and a soft navy shadow.
- **Dark-section cards** (`.exc-card`): 4%-cream translucent fill, 10%-cream border, 4px status-colored left edge, hover lifts −4px.
- Card anatomy: icon (in `--blue-soft` rounded chip) or kicker → bold h3 → one-line muted description.

### Chips & pills
- `.chip` — outlined pill, inverts to navy fill on hover ("Built for" row).
- `.cert` — 12px-radius blue-tinted chip for certifications (ISO, SOC 2).
- `.pill-outline` / `.pill-soft` — uppercase status pills.
- `.ai-tag` — tiny blue badge with `✦` spark marking AI features.

### Numbered rows
`.feature-row` / `.comp-row` — hairline-divided list rows: blue number, (icon,) text. Hover: faint blue wash + 10–14px left-padding slide.

### Confidence ring
SVG circle progress (`.ring`): green stroke, animated `stroke-dashoffset` driven by `data-ring` ratio, tabular-nums percentage centered inside. Used in the floating confidence badge.

### Stats band
`.sec-stats` — 4-up hairline-divided grid: large 800-weight number (animated via `data-count`/`data-decimals`), small muted label. Collapses 4 → 2 → 1 across breakpoints.

### Demo modal
Full-screen blurred navy overlay; `navy-deep` 20px-radius panel with springy entrance (`cubic-bezier(0.34,1.56,0.64,1)`). Translucent inputs that focus to blue border + blue-tinted fill; `#f87171` error states; honeypot anti-spam field; in-place success state. Submits to the backend (`localhost:3001` in dev, Render in production).

### Preloader
Full-screen navy with dual counter-rotating spinner rings, pulsing blue core, 0–100% tabular counter. Swipes up via GSAP; 4s failsafe ensures it never traps the page; skipped entirely under reduced motion.

---

## 6. Motion

**Stack**: GSAP + ScrollTrigger + Lenis smooth scroll + Three.js — all vendored locally (`js/vendor/`), no CDNs. Three.js lazy-loads after the hero image to protect LCP.

**Principle**: everything degrades gracefully — content is fully visible without JS; animation only adds hidden states once libraries are confirmed present (`hasGsap`/`hasST`/`hasThree` guards).

### Vocabulary

| Effect | Spec |
|---|---|
| Reveal (`data-reveal`) | fade-up 44px, 1s `power3.out`, triggered at `top 88%`, once |
| Split headlines (`data-split`) | words wrapped in masked spans, slide up from `yPercent: 110`, 0.9s `power4.out`, 0.045s stagger |
| Hero intro | timeline: title words → eyebrow → sub → CTAs → badges → panel (with 8° rotateX) → chips |
| Counters (`data-count`) | 0 → value, 1.6s `power2.out`, on scroll into view |
| Hero parallax | visual drifts −60px, content fades/sinks on scroll out |
| Compliance parallax | three layered shots scrub at −40/−90/−140px (desktop only, via `gsap.matchMedia`) |
| Floating chips | infinite ±12px sine bob, staggered phase |
| Magnetic buttons | follow cursor ×0.3, release with `elastic.out` |
| Hero panel tilt | ±7°/9° 3D tilt tracking the pointer |
| Custom cursor | ring + dot pair, ring lerps at 0.14, grows on interactive hover — fine pointers only |
| Hover transitions | 0.25–0.35s ease; lifts of −4 to −6px |

### Three.js scenes

1. **Hero particle wave** (`#hero-canvas`): 130×70 grid of blue additive-blended points, layered sine displacement, camera eases toward mouse. Pauses via IntersectionObserver when off-screen.
2. **Security globe** (`#globe-canvas`): dotted sphere (~14k points, Natural Earth land mask from `js/world-land.js`; bright dots on land, faint on ocean), depth-only occluder hiding far-side elements, data-center markers with pulsing amber halos (Dallas, Paris, Bangkok, Singapore), orange great-circle arcs between regions, HTML provider-logo badges projected from 3D each frame, drag-to-spin with inertia plus slow auto-rotation.

### Reduced motion

`prefers-reduced-motion` is honored everywhere: Lenis disabled, all CSS animations/transitions clamped to 0.01ms, preloader hidden, counters/rings render final values immediately, globe auto-rotation and wave motion stop.

---

## 7. Accessibility

- Semantic landmarks (`header`, `main`, `section`, `nav`, `footer`); single `h1`; anchor-linked section IDs.
- `aria-label` on icon-only controls (burger, close, scroll hint); `aria-expanded`/`aria-hidden` kept in sync on menu toggle; modal uses `role="dialog"` + `aria-modal` + `aria-labelledby`, focuses its first input, closes on Escape/backdrop.
- Decorative elements (canvases, chips, glows, cursor) are `aria-hidden`.
- Descriptive `alt` text on every screenshot; status meaning conveyed by label + dot, never color alone.
- Body scroll locks while menu/modal is open.

---

## 8. Voice & Copy Patterns

- Headlines are claims, not labels: *"Built for payroll — not adapted to it"*, *"Know your payroll is ready — before you submit"*.
- Eyebrows name the capability area (*"Exception-first Operations"*, *"Compliance Infrastructure"*).
- Card copy: one bold noun-phrase title + one sentence.
- "Designed to…" / "Built to…" footnotes summarize each section's benefit.
- AI features are consistently marked with the `✦` spark + "AI" tag.
- Footer carries a forward-looking-statement disclaimer (features/timelines illustrative).

---

## 9. File Map

```
index.html          all markup (single page)
css/style.css       full design system + components (tokens at top)
css/fonts.css       @font-face only (also inlined in style.css)
js/main.js          all interaction & motion (IIFE, no modules)
js/world-land.js    Natural Earth land polygons for the globe
js/vendor/          gsap, ScrollTrigger, lenis, three (local copies)
assets/fonts/       Inter woff2 subsets
assets/logos/       logo.svg, logo-white.svg, icon.svg
assets/images/      product screenshots (png + webp variants)
assets/misc/        region flags, datacenter/provider logos
backend/            Node demo-form API + admin portal (Render)
server.py           Python stdlib fallback backend
```

Conventions: no build step, no ES modules, no package.json on the frontend; vendored libraries; kebab-case class names describing components; section-prefixed class namespaces (`exc-`, `conf-`, `comp-`, `sec-`, `cta-`, `demo-`).
