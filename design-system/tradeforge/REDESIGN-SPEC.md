# TradeForge Redesign Specification
**Version:** TF-REDESIGN-002  
**Owner:** Usha (Design)  
**Implementor:** Arjun (Frontend Engineering)  
**Date:** 2026-09-21  
**Status:** READY FOR IMPLEMENTATION

---

## 0. Design Intent

TradeForge is a precision instrument for serious traders — not a consumer app, not a flashy fintech startup dashboard. The design should feel like a Bloomberg terminal that has been humanized: dense, authoritative, and fast, but readable and calm. Every pixel serves information, not decoration.

The one bold choice this design makes: **the hero equity curve**. A slowly-drawing animated chart line that rises from left to right — imperfect, real-looking — with a live P&L counter incrementing in green. This is the single animated "signature moment." Everything else is quiet and disciplined.

**What this design is not:**
- Not glassmorphism backgrounds with blur stacks
- Not a grid of four equal rounded-corner feature cards
- Not acid-green accent on pure-black OLED
- Not tracked-out ALL CAPS eyebrow labels above every heading
- Not scattered scroll-reveal fade-ins on every section

---

## 1. Design Tokens

### 1.1 Color System

The palette departs from the existing indigo (`#4f46e5`) only in the dark surfaces. Indigo is kept as the brand identity. The change is the background register: instead of generic `#111827` grey-dark, use a blue-black that has nautical depth. In light mode, surfaces are cool white with a hint of slate.

#### Dark Theme (default / `data-theme="dark"`)

| Token | Hex | Role |
|---|---|---|
| `--bg-canvas` | `#050C18` | Page canvas, outermost shell |
| `--bg-base` | `#0C1523` | Primary surface (sidebar, page bg) |
| `--bg-raised` | `#13202F` | Cards, panels |
| `--bg-elevated` | `#1A2B3D` | Dropdowns, popovers, modals |
| `--bg-hover` | `rgba(255,255,255,0.04)` | Row hover, nav item hover |
| `--brand` | `#5B52F2` | Indigo brand (active nav, CTA bg, links) |
| `--brand-dim` | `rgba(91,82,242,0.12)` | Active nav bg, selected state bg |
| `--brand-glow` | `rgba(91,82,242,0.25)` | Hero button glow, focus rings |
| `--profit` | `#16DBA1` | Positive P&L, win indicators, green chart lines |
| `--profit-dim` | `rgba(22,219,161,0.12)` | Profit badge backgrounds |
| `--loss` | `#F05252` | Negative P&L, loss indicators |
| `--loss-dim` | `rgba(240,82,82,0.12)` | Loss badge backgrounds |
| `--warning` | `#F4A942` | Partial status, caution |
| `--warning-dim` | `rgba(244,169,66,0.12)` | Warning badge backgrounds |
| `--info` | `#60A5FA` | Info states, links in body text |
| `--text-primary` | `#E2EAF4` | All primary readable content |
| `--text-secondary` | `#7292AA` | Labels, metadata, table headers |
| `--text-muted` | `#3D5469` | Placeholder, disabled text |
| `--border` | `#1C2E42` | Default border on cards and inputs |
| `--border-bright` | `#2A4260` | Visible dividers, focused borders |

#### Light Theme (`data-theme="light"`)

| Token | Hex | Role |
|---|---|---|
| `--bg-canvas` | `#EEF2F7` | Page canvas |
| `--bg-base` | `#FFFFFF` | Primary surface |
| `--bg-raised` | `#F5F8FC` | Cards, panels |
| `--bg-elevated` | `#FFFFFF` | Dropdowns, modals |
| `--bg-hover` | `rgba(0,0,0,0.03)` | Row hover |
| `--brand` | `#4F46E5` | Brand indigo |
| `--brand-dim` | `rgba(79,70,229,0.08)` | Active nav bg |
| `--brand-glow` | `rgba(79,70,229,0.20)` | Focus ring |
| `--profit` | `#059669` | Positive P&L |
| `--profit-dim` | `rgba(5,150,105,0.08)` | Profit badge bg |
| `--loss` | `#DC2626` | Negative P&L |
| `--loss-dim` | `rgba(220,38,38,0.08)` | Loss badge bg |
| `--warning` | `#D97706` | Caution |
| `--warning-dim` | `rgba(217,119,6,0.08)` | Warning badge bg |
| `--info` | `#2563EB` | Info |
| `--text-primary` | `#0E1B27` | Primary text |
| `--text-secondary` | `#4B6278` | Secondary/label text |
| `--text-muted` | `#94A3B8` | Muted/placeholder |
| `--border` | `#DDE5EE` | Default border |
| `--border-bright` | `#BAC8D8` | Strong border |

#### Semantic (same token names, values differ by theme)

Add these to `:root`, overriding in `[data-theme="light"]` and `@media (prefers-color-scheme: dark) :root:not([data-theme="light"])`:

```css
:root {
  /* dark defaults */
  --bg-canvas: #050C18;
  --bg-base: #0C1523;
  --bg-raised: #13202F;
  --bg-elevated: #1A2B3D;
  --bg-hover: rgba(255,255,255,0.04);
  --brand: #5B52F2;
  --brand-dim: rgba(91,82,242,0.12);
  --brand-glow: rgba(91,82,242,0.25);
  --profit: #16DBA1;
  --profit-dim: rgba(22,219,161,0.12);
  --loss: #F05252;
  --loss-dim: rgba(240,82,82,0.12);
  --warning: #F4A942;
  --warning-dim: rgba(244,169,66,0.12);
  --info: #60A5FA;
  --text-primary: #E2EAF4;
  --text-secondary: #7292AA;
  --text-muted: #3D5469;
  --border: #1C2E42;
  --border-bright: #2A4260;
}

[data-theme="light"],
@media (prefers-color-scheme: light) :root:not([data-theme="dark"]) {
  --bg-canvas: #EEF2F7;
  --bg-base: #FFFFFF;
  --bg-raised: #F5F8FC;
  --bg-elevated: #FFFFFF;
  --bg-hover: rgba(0,0,0,0.03);
  --brand: #4F46E5;
  --brand-dim: rgba(79,70,229,0.08);
  --brand-glow: rgba(79,70,229,0.20);
  --profit: #059669;
  --profit-dim: rgba(5,150,105,0.08);
  --loss: #DC2626;
  --loss-dim: rgba(220,38,38,0.08);
  --warning: #D97706;
  --warning-dim: rgba(217,119,6,0.08);
  --info: #2563EB;
  --text-primary: #0E1B27;
  --text-secondary: #4B6278;
  --text-muted: #94A3B8;
  --border: #DDE5EE;
  --border-bright: #BAC8D8;
}
```

### 1.2 Typography

**Primary face:** Plus Jakarta Sans (already loaded). Use `display=swap`.  
**Mono face:** JetBrains Mono — for all financial figures (P&L, R-multiples, win rates, ticker symbols). Load weight 400 and 500 only.

```css
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap');
```

**Type scale:**

| Name | Size | Weight | Line-height | Usage |
|---|---|---|---|---|
| `display-xl` | 56px / 3.5rem | 800 | 1.05 | Landing hero headline |
| `display-lg` | 44px / 2.75rem | 700 | 1.1 | Section headlines |
| `display-md` | 32px / 2rem | 700 | 1.2 | Feature card heads |
| `heading-lg` | 22px / 1.375rem | 600 | 1.3 | Page titles in app |
| `heading-md` | 17px / 1.0625rem | 600 | 1.4 | Card titles, section labels |
| `heading-sm` | 14px / 0.875rem | 600 | 1.4 | Sub-labels, group headers |
| `body-lg` | 17px / 1.0625rem | 400 | 1.6 | Lead paragraphs, hero sub |
| `body-md` | 15px / 0.9375rem | 400 | 1.55 | Default body text |
| `body-sm` | 13px / 0.8125rem | 400 | 1.5 | Secondary content, table cells |
| `label` | 12px / 0.75rem | 500 | 1.4 | Chips, badges, small labels |
| `mono-md` | 15px / 0.9375rem | 500 | 1 | P&L values, R-multiples in app |
| `mono-sm` | 13px / 0.8125rem | 400 | 1 | Table numeric columns |
| `mono-lg` | 22px / 1.375rem | 500 | 1 | Hero P&L counter, stat tiles |

**Numeric rule:** All financial values (P&L, percentages, R-multiples, win rates, prices) MUST use JetBrains Mono (`font-family: 'JetBrains Mono', monospace; font-variant-numeric: tabular-nums;`). This is non-negotiable.

**Line length:** Landing page body paragraphs ≤ 68 characters. App description text ≤ 60 characters.

**Avoid:**
- ALL CAPS labels (use sentence-case with increased weight instead)
- Single-word accent coloring in headlines (`your <span class="text-brand">edge</span>` pattern)
- Tracked-out uppercase eyebrow labels above every heading

### 1.3 Spacing

Use an 8px base grid. Apply only these values:

| Token | px | rem | Usage |
|---|---|---|---|
| `--space-1` | 4px | 0.25rem | Icon gaps, inline micro-spacing |
| `--space-2` | 8px | 0.5rem | Compact padding, chip padding |
| `--space-3` | 12px | 0.75rem | Small component padding |
| `--space-4` | 16px | 1rem | Standard padding |
| `--space-5` | 20px | 1.25rem | Medium component padding |
| `--space-6` | 24px | 1.5rem | Card padding, section gaps |
| `--space-8` | 32px | 2rem | Large section padding |
| `--space-10` | 40px | 2.5rem | Section margins |
| `--space-12` | 48px | 3rem | Hero padding top/bottom |
| `--space-16` | 64px | 4rem | Landing section vertical padding |
| `--space-24` | 96px | 6rem | Hero section vertical |

### 1.4 Border Radius

| Token | Value | Usage |
|---|---|---|
| `--radius-sm` | 4px | Chips, small badges, table chips |
| `--radius-md` | 8px | Inputs, buttons, small cards |
| `--radius-lg` | 12px | App cards, panels |
| `--radius-xl` | 16px | Modals, large landing cards |
| `--radius-2xl` | 20px | Landing hero dashboard frame |
| `--radius-full` | 9999px | Pill buttons, avatar circles |

### 1.5 Shadows

```css
--shadow-sm: 0 1px 3px rgba(0,0,0,0.3), 0 1px 2px rgba(0,0,0,0.2);
--shadow-md: 0 4px 12px rgba(0,0,0,0.25), 0 2px 4px rgba(0,0,0,0.15);
--shadow-lg: 0 10px 30px rgba(0,0,0,0.35), 0 4px 8px rgba(0,0,0,0.2);
--shadow-xl: 0 20px 50px rgba(0,0,0,0.45), 0 8px 16px rgba(0,0,0,0.25);
--shadow-brand: 0 0 0 3px var(--brand-glow);  /* focus ring */
--shadow-profit-glow: 0 0 16px rgba(22,219,161,0.25);  /* hero counter */
```

Light mode: reduce opacity to 40-60% (halve the alpha values).

---

## 2. Component Library

### 2.1 Buttons

Three variants. One size system. No size proliferation.

**Primary** — for the one CTA per screen:
```
Background: var(--brand)
Text: #FFFFFF, 15px, weight 600
Padding: 10px 20px (default), 12px 24px (large landing CTAs)
Radius: var(--radius-md)
Hover: background lightens 8% (use filter: brightness(1.08)), no translate
Focus: box-shadow: var(--shadow-brand), outline: none
Active: filter: brightness(0.94)
Transition: all 150ms ease
```

**Ghost** — secondary actions:
```
Background: transparent
Border: 1px solid var(--border-bright)
Text: var(--text-primary), 15px, weight 500
Padding: 10px 20px
Hover: background var(--bg-hover), border-color var(--brand), color var(--brand)
Radius: var(--radius-md)
Transition: all 150ms ease
```

**Text** — low-prominence:
```
Background: transparent, no border
Text: var(--text-secondary), 14px, weight 500
Hover: color var(--text-primary)
Padding: 6px 8px
```

**Disabled state (all variants):** opacity 0.4, cursor: not-allowed, no hover changes.

**Icon button:**
```
Size: 32×32px (or 28×28px compact)
Radius: var(--radius-sm)
Background: transparent
Hover: var(--bg-hover)
```

### 2.2 Inputs and Forms

```
Height: 38px (compact app inputs), 44px (auth/settings forms)
Padding: 0 12px
Border: 1px solid var(--border)
Radius: var(--radius-md)
Background: var(--bg-raised) (dark) / var(--bg-base) (light)
Font: 14px, var(--text-primary)
Placeholder: var(--text-muted)
Focus: border-color var(--brand), box-shadow var(--shadow-brand)
Error: border-color var(--loss), + error message 12px var(--loss) below
```

Select inputs: use same box styles. Add a custom chevron SVG (12×12) positioned right 12px.

Labels: 13px, weight 500, var(--text-secondary), margin-bottom 6px, sentence case.

### 2.3 Cards

**App card (default):**
```
Background: var(--bg-raised)
Border: 1px solid var(--border)
Radius: var(--radius-lg)
Padding: 20px 24px
Shadow: none by default (border carries the elevation)
```

**Stat tile (P&L, win rate, etc.):**
```
Background: var(--bg-raised)
Border: 1px solid var(--border)
Radius: var(--radius-lg)
Padding: 16px 20px
Value: JetBrains Mono, 22px, weight 500
Label: 12px, weight 500, var(--text-secondary), sentence case
Profit values: color var(--profit)
Loss values: color var(--loss)
```

**Chart card:**
```
Same base as app card
Internal structure: 
  - Card header (16px, weight 600) + optional subtitle (12px, var(--text-secondary))
  - Chart area with 16px padding on all sides
  - Card footer for summary numbers
```

### 2.4 Chips / Badges

**Direction chip:**
```
Long:  bg var(--profit-dim),  text var(--profit),  font-size 12px, weight 500, radius var(--radius-sm), padding 2px 8px
Short: bg var(--loss-dim),    text var(--loss),    same sizing
```

**Status chip:**
```
Open:    bg var(--info)/12, text var(--info)
Partial: bg var(--warning-dim), text var(--warning)
Closed:  bg var(--bg-elevated), text var(--text-secondary)
```

Font: JetBrains Mono 12px for all status/direction chips.

### 2.5 Tables

```
Border: none on the table itself
Row: min-height 44px, border-bottom 1px solid var(--border)
Row hover: background var(--bg-hover)
Header row: background transparent, border-bottom 1px solid var(--border-bright)
Header cells: 12px, weight 500, var(--text-secondary), sentence case (not ALLCAPS)
Data cells: 14px, var(--text-primary)
Numeric cells: JetBrains Mono 13px
Padding: 0 16px per cell (8px on dense tables)
Last row: no border-bottom
```

### 2.6 Navigation (Sidebar)

Width: 224px expanded, 52px collapsed (icon-only).  
Collapsible on tablet (768px–1023px): collapses to icon-only by default.  
Mobile (< 768px): hidden, accessed via a hamburger in the top bar.

Structure:
```
[Brand mark + account selector]
[---divider---]
[Nav items]
[---flex spacer---]
[---divider---]
[Theme toggle]
[User info + logout]
```

**Account selector** (replaces bare brand mark):
```
Logo mark (24×24, SVG) + "TradeForge" text + a compact account name below it (12px, var(--text-muted))
Click → dropdown to switch accounts or create new
Radius: var(--radius-md) on hover
```

**Nav item:**
```
Height: 36px
Padding: 0 12px
Radius: var(--radius-md)
Icon: 16×16, left-aligned, color var(--text-secondary)
Label: 14px, weight 500, var(--text-secondary)
Gap between icon and label: 10px
Active state: bg var(--brand-dim), icon + label color var(--brand), weight 600
Hover state (inactive): bg var(--bg-hover), color var(--text-primary)
```

**Nav groups** (visual grouping without section labels):
```
Group 1: Dashboard, Analytics
Group 2: Trades, Journal, Import
Group 3: Settings  (pushed to bottom)
Between groups: 12px gap + no divider line
```

Add "Journal" to the nav items. It's a built feature that's not currently navigable.

**Collapsed sidebar (icon only, 52px):**  
Show only icons, centered. Tooltip on hover showing the label.

**Mobile top bar** (< 768px):
```
Height: 52px
Left: hamburger icon → opens a drawer (full sidebar slides in from left)
Center: "TradeForge" brand mark
Right: account avatar + theme toggle
Background: var(--bg-base), border-bottom 1px solid var(--border)
```

### 2.7 Theme Toggle

In sidebar footer (app) and navbar (landing page): a minimal icon-only button that switches between sun and moon icons. No label text in the nav (icon is self-explanatory). Show tooltip on hover ("Switch to light/dark mode").

```
Size: 32×32px
Border-radius: var(--radius-md)
Icon: 18×18, centered
Dark mode icon: filled moon, color #818cf8
Light mode icon: filled sun, color #f59e0b
Background on hover: var(--bg-hover)
Transition: 200ms ease (icon swap with opacity fade)
```

### 2.8 Loading States

Skeleton: single animated shimmer strip, not multiple individual boxes per row.

```css
.skeleton {
  background: linear-gradient(90deg, var(--bg-raised) 25%, var(--bg-elevated) 50%, var(--bg-raised) 75%);
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite;
  border-radius: var(--radius-sm);
}
@keyframes shimmer {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}
```

Stat tile skeleton: one 80px×16px bar for label + one 120px×28px bar for value.  
Table skeleton: full-width single bar per row, 16px height.

### 2.9 Empty States

```
Icon: 32×32 SVG (relevant to context — chart icon for empty analytics, document for empty journal)
Headline: 16px, weight 600, var(--text-primary)
Sub: 14px, var(--text-secondary), max 50 chars
Action: primary or ghost button
Center-aligned, 48px vertical padding
```

### 2.10 Error States

```
Icon: alert-triangle SVG, 20×20, color var(--loss)
Message: 14px, var(--loss), left-aligned
No "sorry", no "Oops!" — state what failed and what to do ("Trades failed to load. Refresh to retry.")
```

---

## 3. Landing Page

### 3.1 Layout Overview (Desktop — 1440px wide)

```
┌──────────────────────────────────────────────────┐
│  NAVBAR (sticky, blur on scroll)                 │
├──────────────────────────────────────────────────┤
│  HERO                                            │
│  ┌─── Left 55% ───────┐  ┌── Right 45% ─────┐  │
│  │  Headline           │  │  Dashboard mock   │  │
│  │  Sub-headline       │  │  (animated)       │  │
│  │  CTA buttons        │  │                   │  │
│  └─────────────────────┘  └───────────────────┘  │
│  [Equity curve + P&L counter — full background]  │
├──────────────────────────────────────────────────┤
│  BROKER TRUST STRIP                              │
├──────────────────────────────────────────────────┤
│  PRODUCT VISUAL (full dashboard screenshot)      │
├──────────────────────────────────────────────────┤
│  HOW IT WORKS (3-step horizontal flow)           │
├──────────────────────────────────────────────────┤
│  FEATURES (asymmetric grid)                      │
├──────────────────────────────────────────────────┤
│  ANALYTICS PREVIEW (featured section)            │
├──────────────────────────────────────────────────┤
│  CTA SECTION                                     │
├──────────────────────────────────────────────────┤
│  FOOTER                                          │
└──────────────────────────────────────────────────┘
```

### 3.2 Navbar

```
Position: fixed top-0, full width
Height: 60px
Background: transparent (on scroll top) → var(--bg-base)/90 with backdrop-filter: blur(12px) (after 40px scroll)
Border-bottom: none (top) → 1px solid var(--border) (on scroll)
Transition: background 200ms ease, border-color 200ms ease

Max-width container: 1280px, centered, 32px horizontal padding

Layout:
[Logo mark 24×24 + "TradeForge" 16px weight 700] --------- [Sign in (ghost text)] [Get started (primary btn)]  [Theme toggle icon]

Font: 16px, weight 700, var(--brand) for "TradeForge"
"Sign in": 14px, weight 500, var(--text-secondary), hover: var(--text-primary)
"Get started": primary button, 14px, padding 9px 18px
```

**Mobile (< 768px):**
```
[Logo] ─────── [Theme toggle] [Get started btn compact]
No hamburger — keep it minimal (sign in is discoverable from the CTA)
```

### 3.3 Hero Section

**Background layer (full hero):**
- Background color: `var(--bg-canvas)`
- Background element: a subtle radial gradient centered at top-left, `radial-gradient(ellipse 60% 70% at 5% 30%, rgba(91,82,242,0.06) 0%, transparent 70%)` — very faint brand glow, not a bright bleed

**Animated equity curve (canvas/SVG):**
- Positioned in the right half of the hero, behind the dashboard mockup
- 600×300px canvas element
- On page load: draws a rising equity curve path from left to right over 2.5s. The path uses natural Bezier curves — trends upward overall with authentic variance (small pullbacks, then new highs).
- Stroke: `var(--profit)` / `#16DBA1` in dark mode, `#059669` in light mode, 2px wide
- Opacity: 0.35 (it is background ambiance, not the focus)
- Under the curve: a fill with a vertical gradient from `rgba(22,219,161,0.08)` at top to transparent
- After drawing completes (2.5s), the curve idles with a subtle breathing animation — a very slow vertical offset of ±4px on a 6s ease-in-out loop
- Reduced motion: skip drawing animation, show the final static state immediately

**P&L counter element:**
- Positioned top-right of the canvas area, overlapping the chart
- Text: JetBrains Mono 22px, weight 500, `var(--profit)`
- Prefix: `+₹` then numeric value
- On load (after 0.5s delay): counts up from ₹0 to ₹2,47,850 over 1.8s using an ease-out count (fast start, slow finish)
- After count-up: display a subtle pulsing `text-shadow: var(--shadow-profit-glow)` that breathes every 3s
- Below the number: `↑ +32.4% this month` in 12px, var(--text-secondary)
- Container: semi-transparent `var(--bg-elevated)/60`, backdrop-blur 8px, radius var(--radius-md), padding 10px 14px, border 1px solid `var(--border)`
- Reduced motion: skip count animation, show final number immediately, no pulsing

**Hero content (left column):**

Headline (two lines):
```
Stop trading on instinct.
Build your edge with data.
```
- Font: Plus Jakarta Sans, 52px (desktop), weight 800, var(--text-primary)
- Line-height: 1.06
- No color accent on individual words
- The period at end of line 1 is intentional punctuation rhythm

Sub-headline:
```
TradeForge logs every trade, surfaces your patterns, and shows exactly what's 
working — and what isn't.
```
- Font: 18px, weight 400, var(--text-secondary), max-width 440px, line-height 1.6

CTA group:
```
[Start for free]  [Watch a 2-minute demo]
```
- "Start for free": primary button, 48px height, 24px horizontal padding, 15px font
- "Watch a 2-minute demo": ghost button or text link, 48px height — if video demo exists, opens a modal
- Gap between buttons: 12px
- Below buttons: `No credit card required. Free forever for self-traders.` — 13px, var(--text-muted)

**Dashboard mockup (right column):**
- A browser-framed screenshot or SVG mockup of the TradeForge dashboard
- Frame: `border-radius: var(--radius-2xl)`, subtle `var(--shadow-xl)`, border `1px solid var(--border)`
- Browser chrome bar: 32px, three dots (12×12 circles), solid `var(--bg-elevated)`, `border-radius var(--radius-2xl) var(--radius-2xl) 0 0`
- Content: the actual app UI (dark mode by default), showing the dashboard with stats + a chart
- On load: animates in with `opacity: 0 → 1` + `translateY(16px → 0)` over 600ms, easing `ease-out`, delay 300ms
- The mockup itself does NOT have its own animation — the equity curve behind it provides the motion

**Layout proportions:**
- Left column: `flex: 0 0 55%`, padding-right 48px
- Right column: `flex: 0 0 45%`
- Hero section: min-height 92vh on desktop, padding-top 120px (below fixed nav), padding-bottom 80px
- Content max-width: 1280px, centered

**Tablet (768–1023px):**
```
Stack vertically: headline + sub + CTA on top, dashboard mockup below
Headline: 38px
Mockup: max-width 640px, centered
```

**Mobile (< 768px):**
```
Headline: 30px, two lines
Sub: 16px
CTA: stack buttons vertically, full width
Mockup: hidden (show only the stats panel strip instead)
```

### 3.4 Broker Trust Strip

```
Background: var(--bg-base), border-top + border-bottom 1px solid var(--border)
Padding: 20px 0
Content: centered inline flow

"Works seamlessly with"  [Zerodha logo]  [Upstox logo]  [Angel One logo]

Font: 13px, var(--text-muted), margin-right 24px before logos
Logo containers: 80px wide, height 24px, contain the actual broker logos as SVGs
Gap between logos: 32px
```

Mobile: same but slightly smaller, wrap if needed.

### 3.5 Product Visual Section

```
Background: var(--bg-canvas)
Padding: 80px 0

Headline: "See everything that shapes your edge." — 32px, weight 700, var(--text-primary), centered
Sub: "One dashboard. Every metric that matters." — 17px, var(--text-secondary), centered, margin-bottom 40px

Visual: full-width dashboard screenshot (1280×800 at 2× for retina)
  - Container max-width: 1180px, centered
  - Shadow: var(--shadow-xl)
  - Border-radius: var(--radius-2xl)
  - Border: 1px solid var(--border)
  - On scroll-enter: single reveal — opacity 0→1, translateY(24px→0), 500ms ease-out
    (this is the ONE scroll-reveal on the landing page — use it here where it earns the most)
```

### 3.6 How It Works

This IS a sequence of 3 steps, so numbered markers are appropriate here.

```
Background: var(--bg-base)
Padding: 80px 32px
Max-width: 1100px, centered

Headline: "A feedback loop that compounds." — 32px, weight 700, centered
```

Three steps laid out horizontally on desktop, vertical stack on mobile:

```
┌─────────┐    ──────    ┌─────────┐    ──────    ┌─────────┐
│  [  1 ] │              │  [  2 ] │              │  [  3 ] │
│ Import  │              │ Analyze │              │ Improve │
│ trades  │              │patterns │              │process  │
└─────────┘              └─────────┘              └─────────┘
```

Step card:
```
Number: "01" / "02" / "03" — JetBrains Mono, 13px, weight 500, var(--brand), margin-bottom 12px
Icon: 32×32 SVG icon above the number
Title: 18px, weight 600, var(--text-primary), margin-bottom 8px
Body: 14px, var(--text-secondary), line-height 1.55, max-width 220px
```

Connecting arrows: a simple 32px wide `→` in SVG, centered between cards, color `var(--border-bright)`. Hidden on mobile.

Step details:
- **Import your trades** — "Connect Zerodha, Upstox, or Angel One. Or upload a CSV. TradeForge reconstructs every trade accurately."
- **Analyze your patterns** — "Win rate, expectancy, R-multiples, drawdown, time-of-day — drill into any dimension to find what your P&L is telling you."
- **Improve systematically** — "Journal entries surface behavioral patterns. Discipline scores correlate with outcome. You see exactly where you leak and where you shine."

### 3.7 Features Section

Asymmetric grid — not 4 equal cards. Two large cards on top (the two primary features), three smaller cards below.

```
Background: var(--bg-canvas)
Padding: 80px 32px
Max-width: 1280px, centered

Headline: "Every dimension of your trading, in one place." — 32px, weight 700, centered
Margin below headline: 48px
```

**Layout:**
```
┌──────────────────┬──────────────────┐
│  Trade Journal   │ Analytics        │
│  (large card)    │ (large card)     │
│  480×300px       │ 480×300px        │
├────────┬─────────┴──────────────────┤
│  Risk  │  Import  │  R-Distribution │
│ (small)│  (small) │  (small)        │
└────────┴──────────┴─────────────────┘
```

**Large feature card:**
```
Background: var(--bg-raised)
Border: 1px solid var(--border)
Radius: var(--radius-xl)
Padding: 28px 32px
Height: 300px
Overflow: hidden (inner screenshot shows cropped at bottom)

Layout within card:
  - Tag (small badge): e.g. "Journal" in var(--brand-dim) bg, var(--brand) text
  - Title: 22px, weight 700, var(--text-primary), margin-bottom 8px
  - Body: 15px, var(--text-secondary), max-width 340px
  - Mini screenshot or illustration: positioned absolute, bottom-right, clipped
```

**Small feature card:**
```
Background: var(--bg-raised)
Border: 1px solid var(--border)
Radius: var(--radius-lg)
Padding: 24px
Height: 180px

Icon: 24×24 SVG, color var(--brand), margin-bottom 12px
Title: 16px, weight 600, var(--text-primary), margin-bottom 6px
Body: 13px, var(--text-secondary)
```

Feature card content:

| Card | Title | Body |
|---|---|---|
| Large | **Trade Journal** | "Log every trade with context — your plan, emotions before and after, execution quality, and discipline score. Build the habit of reflection." |
| Large | **Performance Analytics** | "Win rate, expectancy, profit factor, drawdown curves, R-distribution, time-of-day heat maps — every metric updated live as you trade." |
| Small | **Risk Management** | "Track position sizing, portfolio heat, and drawdown tiers before they become problems." |
| Small | **Broker Import** | "CSV or direct import from Zerodha, Upstox, Angel One. No manual entry." |
| Small | **R-Distribution** | "See how your trades cluster around expectancy and where you leave R on the table." |

### 3.8 Analytics Preview Section

```
Background: var(--bg-base)
Padding: 80px 32px
Max-width: 1280px, centered

Layout: two columns, 50/50 (desktop), stacked (mobile)

Left column:
  Headline: "Know your numbers before the market opens."  — 28px, weight 700
  Sub: "Filter by instrument type, direction, date range, or strategy — and see how any slice of your trading performs." — 16px, var(--text-secondary)
  Below: 4 inline metrics (horizontal):
    "64.2% Win Rate" / "2.31R Expectancy" / "1.89 Profit Factor" / "8.4% Max Drawdown"
    Each: JetBrains Mono 20px, weight 500, var(--profit) for the number, 12px label below in var(--text-secondary)
  CTA: "Explore analytics" text link with →

Right column:
  The analytics summary panel — a screenshot or live SVG mockup showing key metrics
```

### 3.9 CTA Section

Not a full-width color band. A contained dark card on a slightly different background.

```
Background: var(--bg-canvas)
Padding: 80px 32px

Inner card:
  Max-width: 720px, centered
  Background: var(--bg-raised)
  Border: 1px solid var(--border)
  Radius: var(--radius-xl)
  Padding: 64px 48px
  Text-align: center

  Headline: "Your edge is built trade by trade." — 32px, weight 700
  Sub: "Join traders who treat their journal as seriously as their setup." — 16px, var(--text-secondary), margin-bottom 32px
  CTA: primary button "Create your account" 48px height + ghost "Sign in" beside it
  Below: "Free to start. No credit card. Works with your existing broker." — 13px, var(--text-muted)
```

### 3.10 Footer

```
Background: var(--bg-canvas)
Border-top: 1px solid var(--border)
Padding: 48px 32px 32px

Max-width 1280px, 3-column layout:

Col 1 (logo + tagline):
  "TradeForge" — 16px, weight 700, var(--brand)
  "A trading journal for people who take data seriously." — 13px, var(--text-muted), max-width 200px
  Theme toggle icon button (same as nav)

Col 2 (links):
  "Product"
  Features  /  Analytics  /  Import  /  Pricing  [placeholder links]

Col 3 (legal):
  © 2026 TradeForge  
  Privacy Policy  /  Terms

Bottom strip: 1px solid var(--border), padding-top 24px, same copyright + links in smaller text for mobile
```

---

## 4. App Pages

### 4.1 App Shell (AppShell)

Replace the current sidebar/main layout with these specs.

**Sidebar (224px):**
```
Background: var(--bg-base)
Border-right: 1px solid var(--border)

Header (56px):
  Padding: 0 16px
  Left: TradeForge logo mark (24×24 SVG) + "TradeForge" 15px weight 700 var(--brand)
  Below logo text: active account name — 11px, var(--text-muted), max-width 180px, truncate

Nav section:
  Padding: 12px 8px
  Groups (visual 12px gap, no label):
    Group A: Dashboard, Analytics
    Group B: Trades, Journal, Import  
    Group C: (spacer flex-1 here)
    Footer items: Settings, [theme toggle], [user + logout]

Nav item height: 36px
Nav item padding: 0 8px
Icon + label gap: 10px
```

**Top bar for mobile (< 768px):**
```
Height: 52px
Fixed position
Background: var(--bg-base)/95, backdrop-blur 8px
Border-bottom: 1px solid var(--border)
Left: hamburger icon (3 lines, 20px, var(--text-secondary)) — opens sidebar drawer
Center: "TradeForge" 15px, weight 700, var(--brand)
Right: account avatar initial in circle 28px (var(--brand-dim) bg, var(--brand) text) + theme toggle icon
```

**Page content area:**
```
Background: var(--bg-canvas)
Overflow-y: auto
Padding: 24px (desktop), 16px (mobile)
```

**Page header pattern:**
Each page starts with:
```
<h1> — heading-lg (22px, weight 600), var(--text-primary)
Optional: breadcrumb or tab row below
Margin-bottom: 24px before first content section
```

### 4.2 Dashboard Page

Redesign the current stacked full-width sections into a proper 2D layout.

**Desktop layout (12-column grid):**
```
Row 1: [P&L hero block — full 12 cols, 160px tall]
Row 2: [Win Rate — 3 cols] [Expectancy — 3 cols] [Profit Factor — 3 cols] [Streak — 3 cols]
Row 3: [Recent Trades — 7 cols] [Recent Journal — 5 cols]
```

**P&L Hero Block (Row 1):**
```
Background: var(--bg-raised)
Border: 1px solid var(--border)
Radius: var(--radius-lg)
Padding: 20px 28px
Layout: left section (all-time P&L large) + center section (MTD + WTD P&L medium) + right section (Capital + Open positions)
Separator: 1px solid var(--border) vertical between sections

All-time P&L:
  Label: "All-time P&L" — 12px, weight 500, var(--text-secondary)
  Value: JetBrains Mono, 32px, weight 500, var(--profit) if positive / var(--loss) if negative

MTD / WTD P&L:
  Label: "MTD" or "WTD" — same label style
  Value: JetBrains Mono, 22px, weight 500, colored by sign

Capital / Open positions:
  Displayed as two smaller stat tiles stacked
```

**Performance stat tiles (Row 2):**
- Same card base
- Value: JetBrains Mono, 26px, weight 500
- Label: 12px, weight 500, var(--text-secondary)
- Streak card: shows win streak in var(--profit) or loss streak in var(--loss) with streak count prominent

**Recent Trades table (Row 3, left):**
```
Card with heading "Recent trades" and a "View all" text link right-aligned
Table with: Date / Symbol / Dir chip / P&L / R
Max 10 rows
Table footer: "View all trades →" link
```

**Recent Journal (Row 3, right):**
```
Card with heading "Recent journal"
Rows: Date / Symbol / Discipline score / Emotion tag
Each row clickable (links to journal entry)
Max 8 rows
Card footer: "View journal →" link
```

**Tablet layout (768–1023px):**
```
Row 1: P&L hero (full width)
Row 2: 2×2 grid for performance stats
Row 3: Trades full width, Journal full width (stacked)
```

**Mobile (< 768px):**
```
All sections stacked, single column
P&L hero: stacked vertically inside the card
Stats: 2×2 grid
Tables: horizontally scrollable with sticky first column (date/symbol)
```

### 4.3 Analytics Page

**Layout:**
```
Filter row (collapsible) → Summary panel → Metric cards grid
```

**Filter bar:**
```
Trigger button: "Filters" with filter icon and active count badge (same as current)
When expanded: 
  Background: var(--bg-raised)
  Border: 1px solid var(--border)
  Radius: var(--radius-lg)
  Padding: 16px
  Filters in a row: Account | Date range | Instrument | Direction | Type | [Clear all]
  Filter inputs use the standard input spec
  On mobile: wrap to two rows
```

**Summary panel** (the `AnalyticsSummaryPanel`):
```
Grid of 8 stat tiles, each following the stat tile spec
Tile values: JetBrains Mono, 26px
Group them visually by category:
  Row 1: Win Rate | Expectancy | Profit Factor | R/R Planned
  Row 2: Total Trades | Max Drawdown | Kelly % | Charges
Border between rows: none — just vertical padding separation
```

**Metric card grid:**
```
2-column grid on desktop, 1-column on tablet/mobile
Each card: 100% width of column
Chart cards follow the "chart card" spec in 2.3
Card order (as currently): R-Distribution, Dimension Breakdown, Risk Summary, Kelly, Time of Day, Rolling Expectancy
```

**Chart card header:**
```
Left: Title (16px, weight 600) + optional tooltip icon (info icon, 14×14, var(--text-muted))
Right: optional period selector (e.g. "30d | 90d | All") as a compact segmented control
Bottom border below header: 1px solid var(--border)
Chart area padding: 0 (charts should touch the card edges except top/bottom 16px)
```

### 4.4 Trades Page

**Filter bar redesign:**
```
Row 1: Status tabs [All | Open | Partial | Closed] (segmented control style, same as current but with the updated styling)
Row 2: [Direction dropdown] [Type dropdown] [From date → To date] [Symbol search] [Clear filters btn (only when active)]
```

Segmented control for status:
```
Container: background var(--bg-raised), border 1px solid var(--border), radius var(--radius-md), padding 3px
Segment button: height 30px, padding 0 12px, radius var(--radius-sm) (inside the container)
Active segment: background var(--bg-elevated), color var(--text-primary), weight 600, shadow var(--shadow-sm)
Inactive: color var(--text-secondary), weight 500
Transition: 150ms ease
```

**Trades table:**
```
Table header: sentence case labels (not UPPERCASE)
Columns: Date / Symbol / Type / Direction / Status / Net P&L / R-multiple / [actions]
Column widths: 
  Date: 90px
  Symbol: 100px
  Type: 90px  
  Direction: 80px
  Status: 80px
  Net P&L: 100px (JetBrains Mono, right-aligned, colored)
  R-multiple: 80px (JetBrains Mono, right-aligned)
Row hover: shows a subtle "→" or arrow icon at the end of the row
```

**Add Trade button:**
```
Position: top right of page header, same row as the "Trades" h1
Style: primary button, 36px height, "Add trade"
Mobile: FAB (floating action button), fixed bottom-right, 52×52px, brand background, + icon
```

**Pagination:**
```
Same position as current (table footer)
"Showing X–Y of Z" — 13px, var(--text-secondary)
Previous / Next buttons as ghost buttons, 32px height
```

### 4.5 Trade Detail Page

(Currently exists but not shown in context. Apply these specs.)

**Layout:**
```
Left: main trade info + fills table (60%)
Right: journal panel (40%)

On mobile: stacked, journal below
```

**Trade header:**
```
Symbol: heading-lg (22px, weight 600) + Direction chip + Status chip inline
Date range: 13px, var(--text-secondary)
Net P&L: JetBrains Mono, 28px, colored by sign — prominent below symbol
R-multiple: JetBrains Mono, 16px, var(--text-secondary) if N/A, var(--profit/loss) if set
```

**Journal panel (right side):**
```
Same card spec as app cards
Header: "Journal" heading + "Edit" text button right-aligned
Discipline score: a horizontal progress bar (0–10 scale), var(--brand) fill, 8px height, radius full
  Below bar: score number + label (e.g. "8 — Disciplined")
Emotion chips: pill shape, each emotion is a colored chip
Mistakes: checkbox-style display (read-only in view mode)
Notes: body text, var(--text-secondary), line-height 1.6
```

### 4.6 Journal (Page — needs creating as a standalone nav destination)

Currently journal is only accessible from trade detail. Add a `/journal` route and page.

**Layout:**
```
Filter: Date range + Symbol search + Discipline score range + Emotion filter
List: table of journal entries (Date / Symbol / Score / Emotions / Excerpt)
Click row → navigates to trade detail with journal expanded
Empty state: "No journal entries yet. Journal your first trade."
```

### 4.7 Import Trades Page

**Layout:**
```
Step flow: [Select broker] → [Upload / Configure] → [Preview] → [Confirm import]
```

Each step shown as a contained card.

**Broker selector:**
```
Grid of broker tiles: Zerodha / Upstox / Angel One / CSV Manual
Each: 140×80px card, broker logo centered, name below
Selected state: border-color var(--brand), background var(--brand-dim), shadow var(--shadow-brand)
```

### 4.8 Settings Page

Sidebar-within-page navigation for settings:

```
Left mini-nav (160px): Profile | Accounts | Preferences | Notifications
Right content (flex 1): selected settings section
```

Each settings section:
```
Section heading: heading-md, var(--text-primary), margin-bottom 16px
Divider: 1px solid var(--border) below heading
Form fields: standard input spec, labeled, 32px vertical gap between fields
Save button: primary, right-aligned, "Save changes"
Success toast: slides in from top-right on save
```

### 4.9 Auth Pages (Login / Register / etc.)

**AuthShell layout:**
```
Full viewport split:
Left half (hidden on mobile): background var(--bg-canvas), shows the TradeForge brand + a quote/tagline + a screenshot of the analytics page
Right half: centered form card

Mobile: full-screen form, no left panel
```

**Left panel content:**
```
Background: var(--bg-canvas)
Top: TradeForge logo mark + name (20px, weight 800)
Center: a large analytics screenshot/illustration
Bottom: A rotating set of metrics e.g.:
  "64.2% win rate tracked across 342 trades."
  "2.31R expectancy. Consistent compounding."
  Displayed as single line, JetBrains Mono, 16px, var(--profit)
  Rotation: 4s per item, crossfade 300ms — only if not prefers-reduced-motion
```

**Form card (right panel):**
```
Max-width: 420px, centered
Background: var(--bg-raised) (light: var(--bg-base))
Border: 1px solid var(--border)
Radius: var(--radius-xl)
Padding: 40px 36px
Shadow: var(--shadow-lg)

Form title: 24px, weight 700, var(--text-primary), margin-bottom 4px
Sub: 14px, var(--text-secondary), margin-bottom 28px
```

---

## 5. Motion Specification

### 5.1 Principles

One orchestrated moment per page. Animate to show change, not to decorate.

- Hover transitions: 150ms ease
- State transitions (open/close, expand): 200ms ease-out
- Page-load reveals: 400ms ease-out (used once per page, hero only on landing)
- Scroll-reveals: ONE reveal on landing page — the product visual screenshot (Section 3.5)
- NO scattered section-by-section fade-ins. NO card hover lifts.

### 5.2 Hero Equity Curve (Landing Page)

```javascript
// Canvas drawing spec
// drawEquityCurve(canvas, options)
// options.duration: 2500ms
// options.points: array of {x, y} normalized 0–1 values
// Preset data (approximate rising curve with variance):
const CURVE_POINTS = [
  {x:0,    y:0.75},
  {x:0.08, y:0.70},
  {x:0.15, y:0.65},
  {x:0.22, y:0.72},
  {x:0.30, y:0.58},
  {x:0.38, y:0.52},
  {x:0.45, y:0.55},
  {x:0.52, y:0.43},
  {x:0.60, y:0.35},
  {x:0.68, y:0.40},
  {x:0.75, y:0.28},
  {x:0.83, y:0.22},
  {x:0.90, y:0.25},
  {x:1.0,  y:0.15},
];
// Animation: requestAnimationFrame loop that draws segments progressively
// After drawing completes: idle breathing via CSS translateY(-4px→0→-4px) on a 6s loop
// Reduced motion: window.matchMedia('(prefers-reduced-motion: reduce)') → skip animation, render final state
```

### 5.3 P&L Counter

```javascript
// countUp(element, targetValue, duration, prefix)
// Ease: easeOutCubic
// Delay: 500ms after page load
// Format: ₹X,XX,XXX using Indian number grouping
// Reduced motion: skip animation, set value directly
function easeOutCubic(t) { return 1 - Math.pow(1 - t, 3); }
```

### 5.4 Navbar Scroll Effect

```javascript
// Add class 'scrolled' to <header> when window.scrollY > 40
// CSS: .scrolled { background: rgba(var(--bg-base-rgb), 0.9); backdrop-filter: blur(12px); border-bottom: 1px solid var(--border); }
// Transition: 200ms ease on background and border-color
```

### 5.5 Product Visual Scroll Reveal

```javascript
// IntersectionObserver on the product visual container
// When 30% of the element enters viewport:
// Add class 'revealed': opacity: 0 → 1, translateY(24px → 0), 500ms ease-out
// Once triggered, never un-reveal
// Reduced motion: apply 'revealed' immediately without transition
```

### 5.6 Auth Page Rotating Metrics

```javascript
// CSS-only crossfade rotation for the left panel metrics
// Each metric gets an animation-delay offset
// @keyframes metricRotate: opacity 0 (0%) → 1 (10%) → 1 (80%) → 0 (100%)
// Reduced motion: show first metric statically, no rotation
```

### 5.7 Sidebar Collapse Transition

```javascript
// Sidebar width animates from 224px → 52px on collapse
// Labels fade out before width collapses (opacity 0, then width)
// Tooltip appears on icon hover when collapsed
// Transition: 200ms ease-out
```

---

## 6. Responsive Breakpoints

| Breakpoint | Width | Layout Changes |
|---|---|---|
| `mobile` | < 768px | Single column, no sidebar (drawer), stacked hero, hidden mockup |
| `tablet` | 768–1023px | Sidebar collapsed to icons, 2-column dashboard grid, stacked hero |
| `desktop-sm` | 1024–1279px | Full sidebar, dashboard in 2-column grid |
| `desktop` | 1280–1439px | Full layout, dashboard 3-column row 2 |
| `desktop-xl` | ≥ 1440px | Max-width container, same layout |

**Touch targets (mobile):** Minimum 44×44px for all interactive elements.  
**Horizontal scroll:** Prohibited on landing page at all breakpoints. App tables may scroll horizontally with overflow-x:auto.  
**No content hidden behind fixed navbars:** Ensure padding-top on first element equals fixed nav height at every breakpoint.

---

## 7. Accessibility Checklist

Every deliverable must pass before merge:

- [ ] All colors meet WCAG AA 4.5:1 for body text, 3:1 for large text / UI components
- [ ] `--profit` `#16DBA1` on `--bg-raised` `#13202F` passes 4.6:1 ✓
- [ ] `--brand` `#5B52F2` on `--bg-canvas` `#050C18` passes 6.2:1 ✓
- [ ] Keyboard navigation: every interactive element reachable via Tab
- [ ] Focus rings visible and distinct: `box-shadow: 0 0 0 3px var(--brand-glow), 0 0 0 1px var(--brand)` — never `outline: none` without an equivalent
- [ ] `aria-label` on icon-only buttons (theme toggle, collapse, close)
- [ ] Skip-to-content link (already exists, maintain it)
- [ ] `role="status"` on loading skeletons
- [ ] `role="alert"` on error messages
- [ ] Canvas equity curve: `aria-hidden="true"` (decorative), `role="presentation"`
- [ ] `@media (prefers-reduced-motion)`: all animations gated, static fallbacks provided
- [ ] Semantic heading hierarchy: h1 → h2 → h3 per page, no skips
- [ ] Broker logos in trust strip: `alt="Zerodha"` etc.
- [ ] Color is never the only indicator (chips have text label + color)

---

## 8. Implementation Notes for Arjun

### Token migration
1. Replace `tokens.css` contents with the new token definitions in Section 1.1
2. Add JetBrains Mono to the font import in `index.css`
3. Update `tailwind.config.ts` to reference the new CSS variable names

### Existing components to update
- `AppShell.tsx` — sidebar redesign per Section 2.6 and Section 4.1
- `LandingPage.tsx` — full rewrite per Section 3
- `DashboardPage.tsx` — layout redesign per Section 4.2
- `AnalyticsPage.tsx` — filter bar and card grid per Section 4.3
- `TradeListPage.tsx` — filter bar and table per Section 4.4

### New components to create
- `EquityCurveCanvas.tsx` — animated equity curve for landing page hero
- `PnLCounter.tsx` — animated counting P&L number
- `StatTile.tsx` — extracted shared stat tile component
- `SegmentedControl.tsx` — reusable tab-like control (used in trades filter, analytics)
- `SidebarNav.tsx` — extracted from AppShell with collapse support
- `ChipDirection.tsx` / `ChipStatus.tsx` — reusable trade chips

### What NOT to change
- API calls, hooks, business logic — zero scope for Arjun
- Test files — Sahadeva will update test coverage post-implementation
- Backend routes, types, schemas

### CSS approach
Continue using Tailwind with CSS variables. Do not add new color values directly to Tailwind class names — always reference tokens. Use `cn()` (via `clsx`/`tailwind-merge`) for conditional class composition.

---

## 9. Deliverable Verification

After implementation, the following must be visually verified in both themes:

- [ ] Landing hero renders with animated equity curve and P&L counter (dark mode)
- [ ] Landing hero shows static final state under prefers-reduced-motion
- [ ] Light mode landing page passes all contrast checks
- [ ] Sidebar collapses correctly on tablet
- [ ] Dashboard grid is 2D on desktop (not stacked)
- [ ] All financial values use JetBrains Mono
- [ ] Direction/status chips render with correct colors and labels
- [ ] Theme toggle persists across page navigation (landing → app)
- [ ] Mobile layouts have no horizontal scroll
- [ ] Focus rings visible on keyboard navigation
