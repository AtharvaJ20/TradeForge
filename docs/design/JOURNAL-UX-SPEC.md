# Journal UX Spec — G5 Deliverable

**Designer:** Usha  
**Status:** Finalised — ready for Arjun implementation  
**Scope:** Step 9, Journal annotation layer (Option A)  
**Covers:** Entry view · Create/edit flow · Pending P&L states · Audit history · Attachments  
**Does not cover:** P&L calculation display (Step 10), R-multiple charting (Karna)

---

## 1. Context & Design Principles

### What the journal is

A journal entry is an annotation layer on top of a reconstructed trade. It captures the trader's *intention* (what they planned) and *reflection* (how they executed and felt). It is not a trade record — the trade record already exists. The journal answers: *Why did I take this trade? How well did I execute my plan?*

### Design principles for this feature

1. **Annotation, not data entry.** The trade facts are already shown. The journal asks one question at a time, not thirty.
2. **Fast first, rich later.** Quick Capture (three taps) ships alongside Full Notes. A journal entry traders skip is worth nothing.
3. **Progressive disclosure for P&L.** P&L is not available until Step 10. The UI must make this legible without feeling broken.
4. **Audit trail without friction.** Change reasons are surfaced *after* saving, not as a gate. Traders who want to record why they edited can; those who don't aren't blocked.
5. **Attachments are optional, never required.** The upload flow must be interruptible at every step.

### Screen contexts

| Surface | Journal renders as |
|---|---|
| Desktop (≥ 1024 px) | Right-side panel (400 px wide), slides in over the trades list when a trade row is selected |
| Tablet (768–1023 px) | Full-height drawer (50% width) |
| Mobile (< 768 px) | Full-screen bottom sheet, pulling up from the trade summary card |

---

## 2. Information Architecture

### Entry point

```
Trades List
│
└── Trade Row (tap / click)
    │
    └── Trade Detail View
        ├── [Tab: Trade]      ← fills, avg entry, reconstruction facts (existing)
        ├── [Tab: Journal]    ← this spec
        └── [Tab: Charts]     ← future
```

On desktop, tabs are replaced by a two-column layout: trade facts (left, 60%) and journal panel (right, 40%).

### Journal tab — page sections (top to bottom)

```
1. TradeContextPanel       ← always visible, non-editable summary from trade record
2. PnlStatusBlock          ← three states; drives plan-price editing
3. Journal Annotation      ← setup name, plan prices, notes
4. Discipline & Behaviour  ← score, mistakes, emotions
5. AttachmentGrid          ← thumbnail grid + uploader
```

---

## 3. Entry View (Read Mode)

### 3.1 Full wireframe — journal entry exists, PENDING_CALCULATION state

```
┌────────────────────────────────────────────┐
│ ← Back to trades                    ⋯  ✕  │  ← Panel header (h=48px)
│ RELIANCE · 23 Aug 2026 · LONG · MIS        │
├────────────────────────────────────────────┤
│ ┌──────────────────────────────────────┐   │
│ │ TRADE CONTEXT                        │   │
│ │ Avg entry    Stop      Target  Qty   │   │
│ │ ₹500.00      ₹490.00  ₹520.00  100  │   │
│ │ Risk: ₹1,000.00   R:R  1 : 2        │   │
│ └──────────────────────────────────────┘   │
│                                            │
│ ┌──────────────────────────────────────┐   │
│ │ 🕐 P&L PENDING                       │   │  ← PnlStatusBlock: PENDING_CALCULATION
│ │ Stop is set. Calculation will run    │   │
│ │ after the session closes.            │   │
│ └──────────────────────────────────────┘   │
│                                            │
│ ─── ANNOTATION ──────────────────────────  │
│                                            │
│ Setup                                      │
│ Bull flag breakout on daily chart          │
│                                            │
│ Planned                                    │
│  Entry ₹500.00  Stop ₹490.00  Target ₹520.00 │
│  Risk  ₹1,000.00                          │
│                                            │
│ Notes                                      │
│ Volume spike confirmed at 10:15. Waited    │
│ for a 5-min close above ₹499.              │
│                                            │
│ ─── DISCIPLINE ──────────────────────────  │
│                                            │
│ Score                                      │
│ ● ● ● ● ● ● ● ○ ○ ○   7 / 10             │
│                                            │
│ Mistakes  (none)                           │
│                                            │
│ Emotions                                   │
│ Before  CALM      During  CONFIDENT        │
│ After   NEUTRAL                            │
│                                            │
│ ─── ATTACHMENTS ─────────────────────────  │
│                                            │
│ ┌───────┐ ┌───────┐ ┌───────┐             │
│ │ chart │ │ chart │ │   +   │             │
│ │  .png │ │  .jpg │ │  Add  │             │
│ └───────┘ └───────┘ └───────┘             │
│                                            │
│ ─────────────────────────────────────────  │
│                                            │
│    [Edit Journal]          [History (2)]   │  ← Footer bar (h=56px)
└────────────────────────────────────────────┘
```

### 3.2 Empty state — no journal entry yet

```
┌────────────────────────────────────────────┐
│ ← Back to trades                    ⋯  ✕  │
│ RELIANCE · 23 Aug 2026 · LONG · MIS        │
├────────────────────────────────────────────┤
│ ┌──────────────────────────────────────┐   │
│ │ TRADE CONTEXT                        │   │
│ │ Avg entry    ━━━━━    ━━━━━    100   │   │  ← stop/target dashes: not yet planned
│ │ Risk: ━━━━━                          │   │
│ └──────────────────────────────────────┘   │
│                                            │
│         📓                                 │
│   No journal entry yet.                    │
│   Annotate this trade to track your        │
│   planning and emotional state.            │
│                                            │
│   [Quick Capture]   [Full Notes]           │  ← two CTAs, same weight
│                                            │
└────────────────────────────────────────────┘
```

**Copy:**
- Heading: `No journal entry yet.`
- Body: `Annotate this trade to track your planning and emotional state.`
- CTA 1: `Quick Capture` (primary)
- CTA 2: `Full Notes` (secondary, same row)

**Note for Arjun:** "Quick Capture" opens the `JournalQuickCapture` sheet. "Full Notes" opens `JournalFullForm`. Both call `PUT /v1/journal/trades/{trade_id}`.

---

## 4. Create / Edit Flow

### 4.1 Quick Capture — 3-field minimum

Triggered by: "Quick Capture" CTA on empty state, or the ⚡ quick-edit icon in the panel header on an existing entry.

```
┌────────────────────────────────────────────┐
│ Quick Capture                           ✕  │  ← Bottom sheet header
│ RELIANCE · 23 Aug 2026                     │
├────────────────────────────────────────────┤
│                                            │
│ How disciplined was this trade?            │
│                                            │
│ ① ② ③ ④ ⑤ ⑥ ⑦ ⑧ ⑨ ⑩               │  ← DisciplineScoreInput
│                          7 selected        │
│                                            │
│ How did you feel?                          │
│                                            │
│ Before                                     │
│ [CALM] [CONFIDENT] [ANXIOUS] [FEARFUL]     │  ← EmotionPicker row
│ [GREEDY] [FRUSTRATED] [EUPHORIC] [BORED]  │
│ [DISTRACTED] [NEUTRAL]                     │
│                                            │
│ Any mistakes?         (optional)           │
│ □ FOMO entry   □ Oversized position        │
│ □ No stop      □ Moved stop wider          │
│ □ Cut winner early  □ Held through stop    │  ← first 6 visible; "Show more" below
│ [Show 7 more]                              │
│                                            │
│ ─────────────────────────────────────────  │
│                    [Save Quick Capture]    │
└────────────────────────────────────────────┘
```

**Interaction notes:**
- Sheet height: 70% of viewport on mobile; 480px fixed on desktop
- Discipline score is the only required field for quick capture; the form can be submitted with score alone
- Emotion chips: single-select per row (before / after treated as one group in quick capture — only "after" is asked; "before" and "during" remain null)
- Quick Capture does not prompt `change_reason` — it is a first-time capture flow

### 4.2 Full Notes form

Triggered by: "Full Notes" CTA, or "Edit Journal" button in the entry view footer.

```
┌────────────────────────────────────────────┐
│ ← Cancel             Edit Journal   Save   │  ← full-screen header on mobile
├────────────────────────────────────────────┤
│                                            │
│ SETUP                                      │
│ ┌──────────────────────────────────────┐   │
│ │ Bull flag breakout                   │   │  ← text input, max 100 chars
│ └──────────────────────────────────────┘   │
│                                            │
│ PLAN                                       │
│                                            │
│ Planned entry (₹)  Planned stop (₹)        │
│ ┌──────────────┐   ┌──────────────────┐    │
│ │ 500.00       │   │ 490.00           │    │
│ └──────────────┘   └──────────────────┘    │
│                                            │
│ Planned target (₹)                         │
│ ┌──────────────────────────────────────┐   │
│ │ 520.00                               │   │
│ └──────────────────────────────────────┘   │
│                                            │
│ Risk at stop  ₹1,000.00  (auto-calculated) │  ← read-only; updates on blur
│                                            │
│ NOTES                                      │
│ ┌──────────────────────────────────────┐   │
│ │ Volume spike confirmed at 10:15.     │   │  ← textarea, no max length
│ │ Waited for 5-min close above ₹499.  │   │
│ │                                      │   │
│ └──────────────────────────────────────┘   │
│                                            │
│ DISCIPLINE SCORE                           │
│ ① ② ③ ④ ⑤ ⑥ ⑦ ⑧ ⑨ ⑩               │
│                          7 selected        │
│                                            │
│ MISTAKES   (select all that apply)         │
│ [FOMO entry]  [FOMO exit]                  │
│ [Oversized position]  [No stop defined]    │
│ [Moved stop wider]  [Cut winner early]     │
│ [Held through stop]  [Revenge trade]       │
│ [Averaging down]  [Entry too early]        │
│ [Entry too late]  [Ignored signal]         │
│ [Distracted]                               │
│                                            │
│ EMOTIONS                                   │
│                                            │
│ Before entering the trade                  │
│ [CALM] [CONFIDENT] [ANXIOUS] [FEARFUL]     │
│ [GREEDY] [FRUSTRATED] [EUPHORIC] [BORED]  │
│ [DISTRACTED] [NEUTRAL]                     │
│                                            │
│ During the trade                           │
│ [CALM] [CONFIDENT] [ANXIOUS] [FEARFUL]     │
│ [GREEDY] [FRUSTRATED] [EUPHORIC] [BORED]  │
│ [DISTRACTED] [NEUTRAL]                     │
│                                            │
│ After closing                              │
│ [CALM] [CONFIDENT] [ANXIOUS] [FEARFUL]     │
│ [GREEDY] [FRUSTRATED] [EUPHORIC] [BORED]  │
│ [DISTRACTED] [NEUTRAL]                     │
│                                            │
├────────────────────────────────────────────┤
│  [Cancel]                        [Save]    │  ← sticky footer
└────────────────────────────────────────────┘
```

**Field validation (client-side):**

| Field | Validation |
|---|---|
| `setup_name` | Max 100 chars; counter shown at 80+ |
| `planned_entry` | Numeric, > 0; optional |
| `planned_stop` | Numeric, > 0; optional; if present, triggers risk calc |
| `planned_target` | Numeric, > 0; optional |
| `discipline_score` | Integer 1–10; required if submitting Full Notes (optional in Quick Capture) |
| `mistakes` | Multi-select; no limit |
| `emotion_before/during/after` | Single-select each; optional |

**Risk calculation display:**
- Shows only when `planned_stop` is set AND the trade has `average_entry`
- Formula: `|average_entry − planned_stop| × total_entry_quantity`
- Label: `Risk at stop  ₹X,XXX.XX  (auto-calculated)`
- Updates on blur of the stop field, not on keystroke
- If `average_entry` is null (trade not yet reconstructed), hide this line entirely

### 4.3 AuditPromptInline — change reason capture

After the user saves an edit to an *existing* entry (not a first-time create), the form closes and an inline toast appears:

```
┌────────────────────────────────────────────────────────┐
│  Entry saved.  Why did you edit it?  (optional)        │
│  ┌────────────────────────────────┐  [Add]  [Dismiss]  │
│  │ Corrected the stop level       │                     │
│  └────────────────────────────────┘                     │
└────────────────────────────────────────────────────────┘
```

**Behaviour:**
- Appears as an inline banner below the panel header, not a modal
- Auto-dismisses after 8 seconds if the user does not interact
- If the user types and taps "Add": fires a second `PUT /v1/journal/trades/{trade_id}` with `change_reason` set and all other fields identical to the previous save (no visible change to the entry itself; only the audit log is updated)
- If the user taps "Dismiss" or it auto-dismisses: nothing is sent; the audit log rows for this edit have `change_reason: null`
- Does **not** appear after Quick Capture (first-time only flows skip it)
- Does **not** block any subsequent action

**Copy:**
- Prompt: `Entry saved. Why did you change it? (optional)`
- Placeholder: `e.g. Corrected the stop level`
- Add button: `Add`
- Dismiss: `Dismiss`

---

## 5. Pending P&L States — PnlStatusBlock

This component is always present at the top of the journal panel (below TradeContextPanel). It is never hidden. Its appearance is driven by `pnl.status` from `GET /v1/journal/trades/{trade_id}`.

### 5.1 PENDING_STOP — no planned_stop set

```
┌──────────────────────────────────────────────────┐
│  ○  Set a stop to unlock R-multiple              │
│     Add your planned stop to calculate           │
│     risk and R-multiple when P&L runs.           │
│                                   [Add Stop →]   │
└──────────────────────────────────────────────────┘
```

**Visual spec:**
- Background: `surface-warning` token (amber-tinted, not alarming)
- Icon: hollow circle `○` (16 px), `color-warning`
- Body text: `color-text-secondary`
- CTA `[Add Stop →]`: text button, `color-warning-emphasis`; tapping it focuses the `planned_stop` field in the Full Notes form (scrolls to it and opens the form if closed)

**Copy:**
- Heading: `Set a stop to unlock R-multiple`
- Body: `Add your planned stop to calculate risk and R-multiple when P&L runs.`
- CTA: `Add Stop →`

### 5.2 PENDING_CALCULATION — stop set, awaiting Step 10

```
┌──────────────────────────────────────────────────┐
│  ◑  P&L calculating                             │
│     Stop is set. Results appear once the         │
│     calculation engine runs after session close. │
└──────────────────────────────────────────────────┘
```

**Visual spec:**
- Background: `surface-info` token (blue-tinted, neutral)
- Icon: half-filled circle `◑` (16 px), `color-info`; animate with a slow 2 s rotation (`prefers-reduced-motion`: static)
- No CTA (nothing for the user to do)
- Do not show a spinner that implies imminent results — the calculation may not run for hours

**Copy:**
- Heading: `P&L calculating`
- Body: `Stop is set. Results appear once the calculation engine runs after session close.`

### 5.3 AVAILABLE — trade_pnl row exists (Step 10 populated)

```
┌──────────────────────────────────────────────────┐
│  ✓  P&L AVAILABLE                               │
│                                                  │
│  Net P&L       R-multiple   Gross    Charges     │
│  ₹+2,150.00    +2.15 R      ₹2,300  ₹150.00     │
└──────────────────────────────────────────────────┘
```

**Visual spec:**
- Net P&L positive: `color-success-emphasis` (green), `font-weight: 600`
- Net P&L negative: `color-danger-emphasis` (red), `font-weight: 600`
- Net P&L zero: `color-text-primary`
- R-multiple: same colour as net P&L; prefixed with `+` for positive
- Gross and Charges: `color-text-secondary`, smaller type (body-sm)
- Background: `surface-success` when profitable, `surface-danger` when loss, `surface-neutral` when flat

### 5.4 SkeletonPnlBlock — loading state

Shown while `GET /v1/journal/trades/{trade_id}` is in flight.

```
┌──────────────────────────────────────────────────┐
│  ░░░░░░░░░░░░░░░░  ░░░░░░░░░░░░░░░░             │  ← shimmer animation
│  ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░          │
└──────────────────────────────────────────────────┘
```

**Spec:** Two shimmer bars. First bar: 40% width. Second bar: 70% width. Height 12 px each, 8 px gap. Shimmer left-to-right, 1.2 s ease-in-out, infinite. Respect `prefers-reduced-motion` — static grey bars, no animation.

---

## 6. TradeContextPanel

Always rendered above the journal. Non-editable. Data comes from the trade record (not the journal API).

```
┌──────────────────────────────────────────────────┐
│ RELIANCE                          LONG  ·  MIS   │  ← symbol + direction badge
│ NSE · 23 Aug 2026 · 09:32 IST                   │  ← exchange, date, first fill time
│                                                  │
│  Avg entry    Stop (plan)   Target (plan)   Qty  │
│  ₹500.00      ₹490.00       ₹520.00         100  │
│                                                  │
│  Planned R:R  1 : 2.0                            │  ← only shown if both stop + target set
└──────────────────────────────────────────────────┘
```

**Props consumed from trade record:**

| Display label | Trade field | Fallback |
|---|---|---|
| Symbol | `instrument.symbol` | — |
| Direction badge | `direction` | — |
| Trade type badge | `trade_type` | — |
| Date + time | `first_fill_at` (IST formatted) | — |
| Avg entry | `average_entry` | `—` |
| Stop (plan) | `journal.planned_stop` | `—` |
| Target (plan) | `journal.planned_target` | `—` |
| Qty | `total_entry_quantity` | — |
| Planned R:R | `(target − entry) / (entry − stop)` | hidden if either is null |

**Note:** `planned_stop` and `planned_target` displayed here come from the **journal entry** (user-set intention), not from the trade record's own fields (which may be null). If the journal entry does not yet exist, show `—` for stop and target.

**Direction badge:**
- `LONG`: background `color-success-subtle`, text `color-success-emphasis`, label `LONG ↑`
- `SHORT`: background `color-danger-subtle`, text `color-danger-emphasis`, label `SHORT ↓`

---

## 7. Audit History Drawer

### 7.1 Trigger

Footer button: `History (N)` where N = count of audit log rows. If 0, button is disabled.

### 7.2 Wireframe

Desktop: slides in from the right as a second panel (320 px wide, full height, over the journal panel).  
Mobile: bottom sheet, 80% height.

```
┌─────────────────────────────────────────┐
│ Change History                       ✕  │  ← drawer header
│ RELIANCE · 23 Aug 2026                  │
├─────────────────────────────────────────┤
│                                         │
│  23 Aug 2026 · 14:30 IST               │  ← changed_at
│  ┌─────────────────────────────────┐    │
│  │ stop         490.00 → 485.00    │    │  ← field_name: previous → new
│  │ notes        (added)            │    │  ← previous was null
│  │ Reason: "Adjusted after re-read"│    │  ← change_reason (if set)
│  └─────────────────────────────────┘    │
│                                         │
│  23 Aug 2026 · 11:15 IST               │
│  ┌─────────────────────────────────┐    │
│  │ discipline_score  8 → 7         │    │
│  │ Reason: (not recorded)          │    │  ← change_reason null
│  └─────────────────────────────────┘    │
│                                         │
│  (older entries…)                       │
└─────────────────────────────────────────┘
```

### 7.3 Grouping

Audit rows are grouped by timestamp proximity: rows written within the same 5-minute window (one save action) are collapsed into a single change card. This avoids showing ten separate rows when a user changed ten fields in one edit.

### 7.4 Field name formatting

| `field_name` from API | Display label |
|---|---|
| `planned_entry` | Planned entry |
| `planned_stop` | Planned stop |
| `planned_target` | Planned target |
| `setup_name` | Setup |
| `notes` | Notes |
| `discipline_score` | Discipline score |
| `mistakes` | Mistakes |
| `emotion_before` | Emotion before |
| `emotion_during` | Emotion during |
| `emotion_after` | Emotion after |

### 7.5 Value display rules

| Scenario | Display |
|---|---|
| `previous_value` is null, `new_value` set | `(added)` in the "before" position |
| `new_value` is null, `previous_value` set | `(removed)` in the "after" position |
| Both values set | `previous → new` |
| `change_reason` is null | `Reason: (not recorded)` — muted text |
| `change_reason` is set | `Reason: "…"` |

### 7.6 Empty state

```
┌─────────────────────────────────────────┐
│ Change History                       ✕  │
│ RELIANCE · 23 Aug 2026                  │
├─────────────────────────────────────────┤
│                                         │
│         📋                              │
│   No edits recorded yet.                │
│   Changes you make to this entry        │
│   will appear here.                     │
│                                         │
└─────────────────────────────────────────┘
```

---

## 8. Attachment Flow

### 8.1 AttachmentGrid — read view

Appears at the bottom of the entry view. Thumbnails are 80 × 80 px tiles in a wrapping flex row, 8 px gap.

```
┌───────┐ ┌───────┐ ┌───────┐ ┌───────┐
│ [img] │ │ [img] │ │ [img] │ │  +    │
│ Entry │ │ Exit  │ │ Entry │ │ Add   │
└───────┘ └───────┘ └───────┘ └───────┘
  AT_ENT   AT_EXIT   AT_ENT
```

- Each tile shows: image thumbnail (object-fit: cover), and below it the `capture_moment` label in caption style
- The `+` tile is the trigger for `AttachmentUploader`; it is always the last tile
- Tapping a thumbnail opens a full-screen lightbox with download button
- Long-press (mobile) or right-click (desktop) shows a context menu: `Download · Delete`

### 8.2 AttachmentUploader — two-step upload flow

**Step 1: File selection**

Triggered by tapping the `+` tile.

```
┌────────────────────────────────────────────┐
│ Add Attachment                          ✕  │
├────────────────────────────────────────────┤
│                                            │
│  ┌──────────────────────────────────────┐  │
│  │                                      │  │
│  │   📷  Tap to select an image         │  │
│  │   JPG · PNG · WEBP · GIF · max 15 MB │  │
│  │                                      │  │
│  └──────────────────────────────────────┘  │
│                                            │
│  When was this taken?                      │
│  ○ At entry    ○ During trade              │
│  ○ At exit     ○ Post review               │
│                                            │
│  Caption  (optional)                       │
│  ┌──────────────────────────────────────┐  │
│  │                                      │  │
│  └──────────────────────────────────────┘  │
│                                            │
│                           [Upload →]       │  ← disabled until file selected
└────────────────────────────────────────────┘
```

**Validation before upload:**
- File type: must be `image/jpeg`, `image/png`, `image/webp`, or `image/gif`. SVG rejected. Other types rejected. Error: `Only JPG, PNG, WEBP, and GIF files are supported.`
- File size: max 15 MB. Error: `File is too large. Maximum size is 15 MB.`
- Extension must match type (e.g. `.png` with JPEG MIME type rejected). Error: `The filename extension doesn't match the file type.`
- `capture_moment` is required. Error shown inline below the radio group: `Please select when this was taken.`
- Validation fires on "Upload →" tap, not on file selection

**Step 2: Uploading (presign → S3 PUT → confirm)**

```
┌────────────────────────────────────────────┐
│ Add Attachment                          ✕  │
├────────────────────────────────────────────┤
│                                            │
│  [thumbnail preview]                       │
│  chart_entry.png · 2.3 MB                 │
│                                            │
│  ████████████░░░░░░░░░░░  65%             │  ← XHR upload progress
│  Uploading…                               │
│                                            │
│                                            │
│  (Cancel)                                  │
└────────────────────────────────────────────┘
```

**Step 3: Confirming (POST /confirm)**

The UI calls confirm immediately after the S3 PUT XHR completes (status 200/204). The user does not see a separate step.

**Step 4: Success**

```
┌────────────────────────────────────────────┐
│ Add Attachment                          ✕  │
├────────────────────────────────────────────┤
│                                            │
│        ✓  Upload complete                  │
│                                            │
│  [thumbnail]  chart_entry.png             │
│                                            │
│  [Add another]              [Done]         │
└────────────────────────────────────────────┘
```

Sheet auto-closes after 2 s if user does not interact.

**Step 5: Failure states**

| Failure | Message | Action |
|---|---|---|
| Presign API error (5xx) | `Couldn't prepare the upload. Try again.` | [Try again] button |
| S3 PUT fails (network) | `Upload failed. Check your connection.` | [Try again] button |
| Confirm API error | `Upload reached the server but couldn't be confirmed. Try again.` | [Try again] |
| File expired (PENDING > 30 min, user left screen open) | `Upload session expired. Please start again.` | [Start over] |
| Trade storage quota full | `Storage full for this trade (75 MB limit reached). Delete an attachment to add more.` | [Done] |
| User storage quota full | `Your storage is full (2 GB limit). Delete attachments to add more.` | [Done] |

**Cancel during upload:**
- Tapping Cancel aborts the XHR
- PENDING row remains in DB (will expire at 30 min per SR-ATT-010)
- Sheet closes; no error shown to user

### 8.3 Attachment delete — confirmation

```
Delete this attachment?
chart_entry.png · AT_ENTRY · 2.3 MB
This cannot be undone.

[Cancel]  [Delete]
```

- Presented as a native `confirm`-style dialog (not a full-screen modal)
- On confirm: `DELETE /v1/journal/trades/{trade_id}/attachments/{attachment_id}`
- On 404: `This attachment has already been deleted.` — dismiss and remove tile
- Thumbnail tile removed from grid immediately (optimistic update)

### 8.4 Lightbox — attachment view

Full-screen overlay. Shows the image at full resolution, centered, with `object-fit: contain`.

```
✕ ─────────────────────────────── ↓ Download

  [image fills the available area]

AT_ENTRY · chart_entry.png · 2.3 MB · 23 Aug 2026
```

- `↓ Download` uses the `download_url` from the API (1-hour pre-signed S3 GET URL, forces download via Content-Disposition)
- Swipe left/right on mobile to move between attachments for this entry
- Pressing Escape (keyboard) or tapping ✕ closes
- URL for the image is never loaded inline as `<img src="…">` using the user-supplied filename — always use the pre-signed `download_url`

---

## 9. Component Catalogue

Ten components for Arjun. Each entry specifies: purpose, inputs, states, accessibility.

---

### C-01 `TradeContextPanel`

**Purpose:** Non-editable summary of trade reconstruction facts. Anchors the annotation to the real trade.

**Props:**
```ts
interface TradeContextPanelProps {
  symbol: string
  exchange: string          // "NSE"
  tradeDate: string         // ISO 8601 date
  firstFillAt: string       // ISO 8601 datetime (display in IST)
  direction: "LONG" | "SHORT"
  tradeType: "MIS" | "CNC" | "CNC_SAME_DAY" | "NRML_FUT" | "NRML_OPT"
  averageEntry: string | null
  totalEntryQuantity: string
  plannedStop: string | null      // from journal entry
  plannedTarget: string | null    // from journal entry
}
```

**States:** Default only. No loading state — this data is fetched alongside the trade row. No empty state — if there is no trade, there is no journal.

**Computed display:**
- Planned R:R: render only when both `plannedStop` and `plannedTarget` and `averageEntry` are non-null
- Formula: `(target − entry) / (entry − stop)`, formatted as `1 : X.X`
- All prices: `₹` prefix, two decimal places, thousands separator with comma

**Accessibility:** All numeric values have `aria-label` with full English description, e.g. `aria-label="Average entry price: ₹500.00"`.

---

### C-02 `PnlStatusBlock`

**Purpose:** Renders the three-state P&L availability indicator.

**Props:**
```ts
interface PnlStatusBlockProps {
  status: "PENDING_STOP" | "PENDING_CALCULATION" | "AVAILABLE"
  netPnl: string | null
  grossPnl: string | null
  totalCharges: string | null
  rMultiple: string | null
  onAddStop?: () => void    // required when status === "PENDING_STOP"
}
```

**States:** Three — see Section 5. Plus loading state (render `SkeletonPnlBlock` instead, from parent).

**Accessibility:**
- AVAILABLE state: `role="region"` `aria-label="P&L summary"`. Net P&L colour is not the only indicator; prefix `+` or `−` sign in the value.
- PENDING_STOP state: the "Add Stop →" button must be keyboard-focusable and trigger `onAddStop`.

---

### C-03 `SkeletonPnlBlock`

**Purpose:** Loading placeholder for `PnlStatusBlock`. Shown while the journal GET is in flight.

**Props:** None.

**Behaviour:** Two shimmer bars (40% and 70% width, 12 px tall, 8 px gap). 1.2 s ease-in-out shimmer. Static when `prefers-reduced-motion` is set.

---

### C-04 `JournalQuickCapture`

**Purpose:** Minimal 1-screen capture — discipline score + after-emotion + optional mistakes. Saves via `PUT /v1/journal/trades/{trade_id}`.

**Props:**
```ts
interface JournalQuickCaptureProps {
  tradeId: string
  onSave: (entry: Partial<JournalEntryWrite>) => Promise<void>
  onClose: () => void
  initialValues?: Partial<JournalEntryWrite>  // pre-fill when editing
}
```

**States:**
- Default: form empty or pre-filled
- Saving: "Save" button shows a spinner, inputs disabled
- Error: inline error banner below the form — `Couldn't save. Try again.`
- Success: sheet closes; parent re-fetches entry

**Required field:** `discipline_score`. The "Save Quick Capture" button is disabled until a score is selected.

---

### C-05 `JournalFullForm`

**Purpose:** Full-field form for creating or editing a journal entry.

**Props:**
```ts
interface JournalFullFormProps {
  tradeId: string
  averageEntry: string | null           // from trade; drives risk calc
  totalEntryQuantity: string            // from trade
  initialValues?: Partial<JournalEntryWrite>
  isEditing: boolean                    // true = show "Edit Journal", false = "Add Journal"
  onSave: (entry: JournalEntryWrite) => Promise<void>
  onCancel: () => void
}
```

**States:**
- Default: inputs empty (create) or pre-filled (edit)
- Dirty: at least one field changed from `initialValues`; Cancel button shows "Cancel (unsaved changes)" on desktop, prompts a native confirm on mobile
- Saving: sticky footer shows spinner; inputs disabled
- Error: error toast anchored to footer
- Success: form unmounts; `AuditPromptInline` shown in parent if `isEditing === true`

**Risk auto-calculate:**
- Recalculate on blur of `planned_stop` field
- Display format: `Risk at stop  ₹X,XXX.XX  (auto-calculated)`
- If `average_entry` is null, display: `Risk: set a stop after entry price is available`

---

### C-06 `DisciplineScoreInput`

**Purpose:** Integer 1–10 score picker. Renders 10 numbered circles.

**Props:**
```ts
interface DisciplineScoreInputProps {
  value: number | null
  onChange: (score: number) => void
  label?: string   // default: "Discipline score"
}
```

**States:**
- Unselected: all circles are empty `○`
- Selected (value = N): circles 1–N filled `●`, circles N+1–10 empty `○`
- Hover (desktop): animate fill on hover
- Disabled: grey, no interaction

**Interaction:** Clicking/tapping circle N sets `value = N`. Clicking the already-selected N again deselects (`value = null`).

**Keyboard:** Arrow keys move focus between circles; Space/Enter toggles selection.

**Accessibility:**
- `role="radiogroup"` with `aria-label` matching the `label` prop
- Each circle is `role="radio"` with `aria-checked` and `aria-label="Score N out of 10"`

---

### C-07 `MistakesCheckboxGroup`

**Purpose:** Multi-select from the 13 `MistakeType` values.

**Props:**
```ts
interface MistakesCheckboxGroupProps {
  value: string[]       // list of selected MistakeType values
  onChange: (selected: string[]) => void
}
```

**Display labels (exact copy):**

| API value | Display label |
|---|---|
| `FOMO_ENTRY` | FOMO entry |
| `FOMO_EXIT` | FOMO exit |
| `OVERSIZED_POSITION` | Oversized position |
| `NO_STOP_DEFINED` | No stop defined |
| `MOVED_STOP_WIDER` | Moved stop wider |
| `CUT_WINNER_EARLY` | Cut winner early |
| `HELD_THROUGH_STOP` | Held through stop |
| `REVENGE_TRADE` | Revenge trade |
| `AVERAGING_DOWN` | Averaging down |
| `ENTRY_TOO_EARLY` | Entry too early |
| `ENTRY_TOO_LATE` | Entry too late |
| `IGNORED_SIGNAL` | Ignored signal |
| `DISTRACTED` | Distracted |

**Layout:** Chip grid (inline-flex, wrapping). Each chip: checkbox + label. Selected chips have `background: surface-danger-subtle`, `border: 1px solid color-danger`.

**In Quick Capture:** Show first 6 only. "Show 7 more" toggle expands the rest.

**In Full Form:** All 13 visible without truncation.

---

### C-08 `AuditHistoryDrawer`

**Purpose:** Slide-in drawer showing the change log for this journal entry.

**Props:**
```ts
interface AuditHistoryDrawerProps {
  tradeId: string
  entryId: string
  isOpen: boolean
  onClose: () => void
}
```

**Data:** Fetched from `GET /v1/journal/trades/{trade_id}/audit` when `isOpen` becomes true. Not pre-fetched.

**States:**
- Loading: three `SkeletonCard` rows (shimmer, same height as a change card)
- Empty: illustration + copy (see Section 7.6)
- Populated: grouped change cards (Section 7.3)
- Error: `Couldn't load history. Try again.` with retry button

**Accessibility:**
- `role="dialog"` `aria-modal="true"` `aria-label="Change history"`
- Focus trapped within the drawer while open; closes on Escape
- First focusable element: the close button `✕`

---

### C-09 `AuditPromptInline`

**Purpose:** Optional change-reason capture shown as an inline banner after saving an edit.

**Props:**
```ts
interface AuditPromptInlineProps {
  onSubmit: (reason: string) => Promise<void>
  onDismiss: () => void
  autoDismissMs?: number  // default: 8000
}
```

**States:**
- Idle: banner visible, input empty
- Typing: input active; auto-dismiss timer paused
- Submitting: input and Add button disabled, spinner
- Submitted: banner replaces itself with `Reason added.` for 2 s, then unmounts
- Auto-dismissed: unmounts silently

**Layout:** Full-width inline bar, height 56 px (one-line). `input` + `[Add]` + `[Dismiss]` in a single flex row.

---

### C-10 `AttachmentUploader`

**Purpose:** Two-step file upload (presign → XHR → confirm) presented as a sheet.

**Props:**
```ts
interface AttachmentUploaderProps {
  tradeId: string
  onComplete: (attachment: AttachmentView) => void
  onClose: () => void
}
```

**Internal state machine:**

```
IDLE → FILE_SELECTED → UPLOADING → CONFIRMING → SUCCESS
                 ↓           ↓
             VALIDATION_ERROR  UPLOAD_ERROR
                                    ↓
                               (RETRY → UPLOADING)
```

**IDLE → FILE_SELECTED:** User picks a file via `<input type="file" accept="image/jpeg,image/png,image/webp,image/gif">`. Client validates type, size, extension immediately (before showing the Upload button).

**FILE_SELECTED → UPLOADING:**
1. POST `presign` endpoint → receive `upload_url`, `attachment_id`, `s3_key`
2. XHR PUT to `upload_url` with `Content-Type` header set to the file's MIME type
3. Track progress via `xhr.upload.onprogress`

**UPLOADING → CONFIRMING → SUCCESS:**
1. XHR completes (status 200 or 204)
2. POST confirm endpoint with `attachment_id`
3. On 200: emit `onComplete(attachment)`, show SUCCESS state

**Cancel during UPLOADING:** `xhr.abort()` → return to IDLE, close sheet.

**Retry behaviour:** From `UPLOAD_ERROR` state, "Try again" button returns to `FILE_SELECTED` (file is still in memory, user does not need to re-pick).

**Accept attribute note:** The `<input accept>` filter is UI-level guidance only. Server-side validation is authoritative. A malicious user who bypasses the accept filter will receive a `422` from the API.

---

## 10. State Matrix

| Scenario | PnlStatusBlock | Entry section | Footer |
|---|---|---|---|
| Loading | `SkeletonPnlBlock` | skeleton rows | disabled |
| No journal entry | hidden | empty state illustration + two CTAs | hidden |
| Entry exists, no stop | PENDING_STOP with CTA | annotation content | `[Edit Journal]` `[History (N)]` |
| Entry exists, stop set, no P&L | PENDING_CALCULATION | annotation content | `[Edit Journal]` `[History (N)]` |
| Entry exists, P&L available | AVAILABLE with figures | annotation content | `[Edit Journal]` `[History (N)]` |
| API error on load | — | error banner + retry | — |

---

## 11. Responsive Behaviour

### Mobile (< 768 px)

- Journal renders as a **full-screen bottom sheet**, pulling up from the trade summary card in the list
- Tabs replaced by back-navigation: "← RELIANCE · 23 Aug" in the header
- `JournalFullForm`: full-screen, scrollable, sticky footer with Cancel/Save
- `AuditHistoryDrawer`: full-screen bottom sheet (100% height)
- `AttachmentUploader`: full-screen bottom sheet
- Emotion picker chips wrap to two rows; do not truncate
- `MistakesCheckboxGroup` chips: two columns, no truncation in Full Form; 6-max with "Show more" in Quick Capture

### Tablet (768–1023 px)

- Journal renders as a **50%-width side drawer** from the right
- Same layout as mobile inside the drawer

### Desktop (≥ 1024 px)

- Trade detail is a **two-column page**: trade context left (60%), journal right (40%)
- `AuditHistoryDrawer` slides in as a third panel to the right of the journal panel (320 px), pushing no layout — rendered as an overlay on top with a scrim behind it
- `JournalFullForm` renders inline within the journal panel (no sheet), replacing the read view

---

## 12. Accessibility Checklist (for Arjun to verify)

- [ ] All interactive elements reachable by keyboard Tab/Shift-Tab
- [ ] `DisciplineScoreInput` navigable by arrow keys
- [ ] `MistakesCheckboxGroup` chips are checkbox inputs (not divs) with visible focus ring
- [ ] `AuditHistoryDrawer` traps focus and closes on Escape
- [ ] `AttachmentUploader` file input is keyboard-accessible (`<label>` wrapping or `for` attribute)
- [ ] Colour is never the only indicator of meaning: P&L sign uses `+`/`−` prefix; direction uses text label in addition to colour
- [ ] All shimmer/loading animations respect `prefers-reduced-motion` (static greys, no animation)
- [ ] Images in the attachment grid and lightbox have `alt` attributes; use `filename` as fallback alt text
- [ ] `download_url` used for image `src` in lightbox (never raw S3 key as a URL)
- [ ] Change history drawer announces itself with `role="dialog"` `aria-modal="true"`

---

## 13. Handoff Notes to Arjun

### API boundary

| Action | Method | Endpoint | Commits |
|---|---|---|---|
| Read entry + P&L status + attachments | GET | `/v1/journal/trades/{trade_id}` | No |
| Create or update entry | PUT | `/v1/journal/trades/{trade_id}` | Yes |
| Read audit history | GET | `/v1/journal/trades/{trade_id}/audit` | No |
| Request upload URL | POST | `/v1/journal/trades/{trade_id}/attachments/presign` | Yes |
| Confirm upload | POST | `/v1/journal/trades/{trade_id}/attachments/{id}/confirm` | Yes |
| Delete attachment | DELETE | `/v1/journal/trades/{trade_id}/attachments/{id}` | Yes |

### `user_id` is never sent in a request body or URL

The backend derives `user_id` from the session cookie. The frontend must never include it in any request payload or path parameter.

### Optimistic updates

- Attachment delete: remove tile immediately; reverse on 4xx
- Quick Capture save: show optimistic updated score immediately; reverse on error
- Audit log count in footer button: increment by 1 after a successful edit save with at least one changed field; exact count re-fetched on next GET

### Error handling

- All `422` responses from the journal API are user-visible validation errors (content type, size, quota). Display the `detail` field from the response body as the error message.
- `404` on attachment confirm/delete: treat as already-deleted; remove from UI without error message.
- `503` (Redis unavailable): display `Service temporarily unavailable. Please try again.` — do not expose the reason.

### StubStorage note (development only)

Until Nakula wires the real S3 bucket, the upload URLs will be `https://stub-s3.local/…`. The XHR PUT to this URL will fail (connection refused). During development, mock the XHR step: treat any presign success as an upload success, then call confirm immediately. Remove this mock before staging.
