# Design Brief: Fact Knowledge Layer UI
## Visually native to Superjoin — derived from superjoin.ai

---

## 0. Method & an honest caveat

This brief is built from what's actually visible on `superjoin.ai` and its product screenshots: page structure, section copy, layout rhythm, iconography style, and color usage as rendered. It's a real Framer-built site, and I don't have browser DevTools access in this environment to pull exact computed hex values or the shipped font-family declaration — so the palette and type spec below are **close, deliberate approximations**, not pixel-extracted values. Before final implementation, it's worth a two-minute pass with your browser's inspector on the live site to confirm the exact hex codes and font stack; everything else in this brief (layout logic, component patterns, tone, the semantic color mapping for your own facts/relationships) holds regardless.

**One assumption stated up front:** I'm designing this as a standalone web app that looks and feels like it belongs in the Superjoin product family — matching their marketing site / dashboard register. Superjoin's actual live product also exists as a narrow sidebar panel *inside* Google Sheets, which is a meaningfully different layout problem (300–400px fixed width, no marketing chrome). If what you actually want is "make it look like their in-Sheets copilot panel," say so and I'll redo the layout section for that width — the color/type/voice system below carries over either way.

---

## 1. What Superjoin's actual identity is (not a generic SaaS default)

Grounding this in the subject matter, per the brief itself: Superjoin is a **spreadsheet tool wearing a calm, human-support voice**, not a flashy AI startup. Reading the real site:

- The product literally lives inside Google Sheets — the visual world is **grids, cells, data flowing in**, not abstract gradient blobs or neural-network imagery.
- The copy register is conversational and slightly self-deprecating ("More useful than the last intern you hired," "no sales pitch, we promise," "Ditch CSVs"), never hypey AI jargon. This should show up in your UI copy, not just the marketing site's.
- Feature communication leans on **small, friendly icon tiles in soft pastel colors** (mint, lavender, peach, sky blue) rather than one loud brand color hammered everywhere — the palette is *plural and gentle*, not a single neon accent.
- Trust is signaled quietly: rating badges, logo walls, testimonial cards with real names/titles/companies — understated social proof, not big bold claims.
- Rounded, soft-edged UI throughout (buttons, cards, icon containers), generous whitespace, no hard black-on-white harshness anywhere.

The specific trap to avoid (and the reason this section exists): a generic "AI SaaS" reskin would reach for cream-background-plus-terracotta-accent, or a single loud brand-green hammered on every element, or ALL-CAPS section eyebrows and em-dash labels. Superjoin's actual site does none of that — it's closer to **a calm productivity tool that happens to use AI**, and your UI should read the same way: the star of the page is the facts and evidence, not the "AI-ness" of the system.

---

## 2. Color system

| Token | Approx. hex | Role |
|---|---|---|
| `--bg-canvas` | `#FFFFFF` / `#FBFBFA` | Page background — near-white, not stark, not cream-warm |
| `--bg-surface` | `#F7F7F5` | Card/panel background, one step off canvas |
| `--text-primary` | `#14161A` | Body/heading text — soft near-black, never pure `#000` |
| `--text-secondary` | `#5B5F66` | Captions, metadata, secondary copy |
| `--border-subtle` | `#E8E8E5` | Hairline dividers, card borders |
| `--brand-green` | `#1E8E5A` (approx.) | Primary action color — Superjoin's own accent; use sparingly, on primary CTAs and the one or two things that should draw the eye |
| `--pastel-mint` | `#D9F2E4` | Icon-tile background 1 |
| `--pastel-lavender` | `#E6E1F9` | Icon-tile background 2 |
| `--pastel-peach` | `#FCE8D9` | Icon-tile background 3 |
| `--pastel-sky` | `#DCEEFB` | Icon-tile background 4 |

**Your own semantic layer, mapped onto that same gentle-pastel logic rather than stoplight-red/green:**

| Relationship | Color | Reasoning |
|---|---|---|
| Corroborates | `--brand-green` on `--pastel-mint` | Reuses Superjoin's own accent — corroboration is the "everything's working" state |
| Contradicts | Muted coral `#D9603E` on soft peach `#FCE3D6` | A warm alert, not a harsh stop-sign red — matches the site's avoidance of harsh color |
| Reconciled by context | Muted amber `#B8842A` on pale gold `#F5EBD3` | "Resolved, with a story" — distinct from both the settled-green and the alert-coral |
| Unrelated / low confidence | `--text-secondary` on `--bg-surface` | Deliberately quiet — this is the "nothing to see here" state and shouldn't compete visually |

This gives you four states that read instantly apart at a glance (which matters — your evaluator will be scanning many relationship rows quickly) while staying inside the same soft, desaturated register as the rest of the palette. Nothing here is neon or saturated; that's the deliberate match to "soothing," not an accident.

---

## 3. Typography

Superjoin's site uses a geometric-humanist sans throughout headings and body — clean, slightly rounded terminals, comfortable at both display and small caption sizes. The closest freely-licensable match to implement with is **Inter** (variable weights 400–700), which is what I'd actually ship with absent the exact confirmed font-family from the live CSS. If you inspect the site and it turns out to be a different (possibly paid/custom) typeface, swap the family only — the scale and weight logic below transfers directly.

| Role | Size / weight | Notes |
|---|---|---|
| Page title | 28–32px / 600 | One per screen, not per card |
| Section heading | 20px / 600 | "Facts," "Relationships," "Evidence" |
| Card title / fact attribute | 16px / 600 | |
| Body / evidence quote | 15px / 400, line-height 1.6 | Quotes get slightly more line-height than UI chrome — they're the thing being read carefully |
| Caption / metadata | 13px / 500 | Page numbers, confidence scores, timestamps — `--text-secondary` |

No all-caps labels anywhere (the skill-level default to avoid, and also just not what the real site does — its labels are sentence case throughout). No single-word-in-a-headline color accenting.

---

## 4. Shape, spacing, elevation

- **Radius:** 12px on cards and panels, 8px on buttons/inputs, 999px (full pill) on status badges and rating-style chips — matches the rounded-everything softness of the real site.
- **Shadow:** one soft ambient shadow only — `0 1px 2px rgba(20,22,26,0.04), 0 4px 12px rgba(20,22,26,0.06)` — used on elevated surfaces (modals, the evidence-quote popover), not stamped under every card. Flat cards on `--bg-surface` with a `--border-subtle` hairline are the default; reserve shadow for things that are genuinely floating above the page (a quote tooltip, a modal).
- **Spacing scale:** 4 / 8 / 12 / 16 / 24 / 32 / 48px. Generous whitespace between sections (48px+) — the real site never feels cramped.
- **Icon tiles:** small (36–40px) rounded-square containers in one of the four pastel backgrounds, one icon glyph per tile, matching the feature-grid pattern from the homepage — reuse this exact pattern for your fact-type icons (a financial-metric fact gets a mint tile, a director-appointment fact gets a lavender tile, etc.) rather than inventing a new iconography language.

---

## 5. Component patterns, mapped to your actual screens

### Upload / ingestion screen
- Centered, generous drop zone (matches the site's hero-centric, single-focal-point layout), not a cramped form.
- Status uses plain language in the interface's own voice, not a spinner-and-percentage only: "Reading pages 40 of 100," "Pulling out facts," not "Processing... 40%." This matches the conversational tone the skill calls for and the real site's own copy voice.

### Fact browser (list/table view)
- Rows, not a wall of identical rounded cards (the "SaaS-card-kit" trap) — a clean table with a colored icon tile per fact type, the attribute + value as the primary line, and a `--text-secondary` caption line underneath for source doc + page. Click a row to expand the evidence quote inline rather than always navigating away.

### Evidence panel
- The verbatim quote renders in a distinct visual treatment — a left border in `--border-subtle` (not a full boxed callout, which would compete with the coral/amber relationship colors elsewhere) with page number and source document as a caption above it.
- If the quote-validation step (see your TRD) flagged low confidence, show that inline as a small quiet caption ("Quote could not be verified against source text"), never as a red error banner — this is calibration/uncertainty, not failure, and the visual weight should match that.

### Relationships tab
- Two facts shown side by side (or stacked on narrow viewports), connected by a small pill badge using the four-state semantic palette from §2, with the explanation as a single readable sentence beneath — this *is* the part of your product doing the most work, so give it the most visual clarity and the least decoration.

### Navigation / chrome
- A slim top bar: wordmark left, a couple of plain-text nav items, one primary green button right — mirrors the real site's header rhythm (logo, a few links, one CTA) rather than a heavy sidebar-and-topbar combo. Keeps the "seamlessly Superjoin" feeling without you having to reverse-engineer their internal app chrome, which you can't see anyway.

---

## 6. Voice and copy (applies to your UI text, not just this brief)

Pulling directly from the skill's writing guidance and the real site's own register:
- Buttons say exactly what happens: "Upload PDF," "View evidence," not "Submit" or "Learn more."
- Empty states are an invitation, not an apology: "No facts extracted yet — upload a PDF to get started," not "Oops, nothing here."
- Errors state what happened plainly: "Couldn't verify this quote against the source page," not "Something went wrong."
- Keep it conversational and slightly warm, the way "more useful than the last intern you hired" is warm — but don't force jokes into a rubric-graded evidence panel; save personality for onboarding/empty-state copy, keep the fact/evidence surfaces plain and legible.

---

## 7. What to actually verify before you build

- [ ] Open superjoin.ai in a browser, inspect the `<body>` computed `font-family` and the CSS custom properties (Framer sites often expose them as `--framer-*` variables) to lock exact hex values in place of the approximations in §2.
- [ ] Confirm whether "seamlessly integrable" means the marketing-site register (this brief) or the in-Sheets sidebar register (narrower, denser, no marketing chrome) — flag this back if it's the latter.
- [ ] Sample the real site's button/input radius with a ruler tool (browser inspector "computed" tab) if you want to match 12px vs. 8px vs. 10px exactly rather than the approximation above.
