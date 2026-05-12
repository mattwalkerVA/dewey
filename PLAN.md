# Plan v2: Browser-loaded Lesson Planner (anchored on existing Dewey)

## What changed since v1
Three commits landed on `main` that significantly reshape the design:
- **`teaching_tools/`** — 55 printable HTML cards from mattwalker.education
  (discussion move cards, structured interactions template, dual-objective
  planner, dual-lens rubric, exit-ticket differentiator, WIDA × Zwiers
  matrix, co-teaching suite, etc.).
- **`dashboard/`** + `dashboard_server.py` — a React SPA (via `htm` + ESM
  CDN, **no build step**) with views for Library, Profile, Standards, Save
  Plan, served by stdlib `http.server`.
- **`data/`** — `va_sols.json` and `wida_descriptors.json`, queried by
  `tools/standards.py`.

The right move is **not** a parallel Vite+Tailwind app. It's to add a
**Plan Lesson** view to the existing dashboard and a **POST /api/lesson**
endpoint to `dashboard_server.py`, and to bake the teaching_tools
vocabulary into the lesson-generator prompt.

## Design contract

### Input form (new "Plan Lesson" view in `dashboard/app.js`)
- `standard` — autocomplete against existing `GET /api/standards`
- `objective` — free text
- `prompt` — free text (teacher's specific ask / context)
- `grade` — K–12 dropdown
- `subject` — ELA · Math · Science · Social Studies · Other
- `widaLevels` — dual-thumb range, 1–6
- `klu` — Key Language Use: **Narrate · Inform · Explain · Argue**
  (from the WIDA × Zwiers 5×4 framework)
- `timeMinutes` — segmented toggle, **45** or **90** only

### Lesson skeleton (timing sums to budget exactly)
Anchor on the **three moments** from `structured-interactions-lesson.html`:

| Moment | 45-min | 90-min | Required student discussion |
|---|---|---|---|
| **Preparing** | 10 min | 15 min | **Discussion 1** — activate / anticipate |
| **Interacting** | 25 min | 55 min | **Discussion 2** — deepen / push back |
| **Extending** | 10 min | 20 min | **Discussion 3** — synthesize / transfer |

Three moments → exactly three discussion pieces. Turn-and-Talk is the floor;
the generator should choose a richer protocol per moment when content
supports it (see palette below).

### Discussion-protocol palette (drawn from teaching_tools)
Each discussion piece must name a protocol. The generator picks from:

- **Discussion Move Cards** (`co-teaching/10-discussion-move-cards.html`):
  Probe · Paraphrase · Build · Challenge · Clarify — distribute and require
  ≥2 moves per student.
- **Turn-and-Talk** (floor) — pair + 60–90s timed exchange + 1 share-out.
- **Stronger & Clearer Each Time** (Zwiers) — pair → rotate → rewrite.
- **Jigsaw** (`jigsaw-project-matrix.html`) — expert + home groups; only
  in 90-min lessons.
- **Anticipatory Guide** discussion
  (`anticipatory-guide-expressions.html`) — pre-reading, agree/disagree
  with formulaic expressions.
- **Write-Converse-Write** (`write-converse-write-assessment.html`) —
  quick-write → partner talk → revised quick-write.
- **Source Triangulation** discussion (`co-teaching/13-...html`) — 3
  sources, compare evidence.
- **Visual-First Reading** discussion (`co-teaching/14-...html`) —
  describe before reading.
- **Quick-Writes by Level** (`co-teaching/16-...html`) — leveled stem +
  partner share.

For each piece the model emits:
- **Protocol name** (from palette)
- **Prompt** (open, content-anchored, productive)
- **Sentence stems by WIDA level** — for every level in the requested
  range, drawn from `data/wida_descriptors.json` where applicable
- **Move cards in play** — which of Probe/Paraphrase/Build/Challenge/Clarify
  students must use
- **Timing** (sums to moment budget)
- **Teacher move** — what to listen for, when to cold-call
- **Companion tool** — relative link to a `teaching_tools/*.html` printable

### Objectives + Assessment (dual-lens)
Use the **Dual-Objective Co-Planning** template's structure
(`co-teaching/02-dual-objective-planner.html`):
- **Content objective** (Students will know / do…) + **Standard**
- **Language objective** (Students will use language to…) + **WIDA KLU**
- **Evidence (content)** and **Evidence (language)** — separate
- **Dual-Lens Rubric** (`co-teaching/19-dual-lens-rubric.html`) attached
- **Exit ticket** generated via **Exit Ticket Differentiator** pattern
  (`co-teaching/18-...html`) — one stem per WIDA level in range

### Excellent teaching tactics required by the prompt
- Gradual Release across the three moments (I do / We do / You do)
- Comprehensible input: visuals, realia, cognates (link
  `co-teaching/08-cognate-bridge.html` when languages of origin known)
- Wait time ≥5s; cold-call with thinking time
- Productive struggle with scaffolds you can fade
- Formative checkpoint at every moment transition (named, observable)
- One Zwiers academic-language skill exercised
  (elaboration · fortification · persuasion · negotiation)
- No student PII; design at the proficiency-level grain

## Architecture

```
dashboard/index.html  ──static──>  user
dashboard/app.js      (htm + React via ESM CDN, no build)
        │
        ├─ POST /api/lesson   (NEW, streamed)
        ├─ GET  /api/plans    (existing)
        ├─ POST /api/plans    (existing — saves the generated lesson)
        ├─ GET  /api/standards (existing)
        └─ GET  /api/wida     (existing)

dashboard_server.py   (stdlib http.server — extend with /api/lesson)
        │
        └─ calls anthropic SDK with LESSON_PLAN_SYSTEM_PROMPT,
           streams chunks back via chunked transfer encoding
```

Decision reversal from v1:
- **No Vite, no Tailwind, no FastAPI.** The existing stack is already
  browser-loaded React; we extend it.
- **No IndexedDB.** Saved lessons already persist via `POST /api/plans`
  → `plans/*.md` on disk. The teacher profile already lives in the
  SQLite memory store and is exposed via `GET /api/profile`.
- The FERPA filter in `agent.py` is reused by the new endpoint.

## Implementation phases

### Phase 1 — Backend endpoint
- `dashboard_server.py`: add `POST /api/lesson` handler that:
  1. Parses JSON body (validate fields, clamp WIDA, enforce time ∈ {45,90}).
  2. Runs FERPA filter on free-text fields.
  3. Loads relevant WIDA descriptors for the requested level range + KLU
     from `tools/standards.search_wida`.
  4. Loads the standard's full text via `tools/standards.search_standards`
     if `standard` looks like a SOL code.
  5. Builds a system prompt from `LESSON_PLAN_SYSTEM_PROMPT` (new in
     `prompts.py`).
  6. Calls Anthropic with streaming; writes `text/event-stream` chunks.
  7. After completion, validates: exactly 3 `### Discussion` sections,
     timings sum to budget, every WIDA level in range has stems. Retries
     once with a corrective system message if validation fails.
- `tests/test_dashboard_server.py`: add cases for validation, FERPA, and
  the retry path.

### Phase 2 — New "Plan Lesson" view
- `dashboard/app.js`: add `"plan"` to the `views` array, add a
  `PlanLesson` component:
  - The form described above.
  - SSE consumer that appends streamed markdown to a live `<pre>`.
  - On completion: a "Save to Library" button that POSTs to `/api/plans`
    with `{title, grade, subject, content}`.
  - A "Companion tools" sidebar that links the generated plan's tool
    references (e.g., "Discussion Move Cards") to their
    `/teaching_tools/...html` paths (served as static files — add a
    static handler to `dashboard_server.py`).
- `dashboard/styles.css`: add styles for the form, the streaming pane,
  and the discussion-piece card (mirror the teaching_tools aesthetic —
  DM Sans, navy `#1a1a2e`, accent colors from the move cards).

### Phase 3 — Static serving of teaching_tools
- `dashboard_server.py`: route `/teaching_tools/*` to the existing
  files. They're already self-contained printable HTML.
- In the streamed lesson, anchor every protocol reference to its tool:
  `[Discussion Move Cards](/teaching_tools/co-teaching/10-discussion-move-cards.html)`.

### Phase 4 — Prompt
Add to `prompts.py`:

```python
LESSON_PLAN_SYSTEM_PROMPT = """\
You are Dewey, drafting one class-period lesson for a K-12 teacher who
serves multilingual learners. Anchor the lesson on the three moments
from the Structured Interactions framework: PREPARING, INTERACTING,
EXTENDING. Within each moment include exactly one student discussion
piece, for a total of THREE discussion pieces in the lesson.

INPUT
- Standard: {standard}
- Content objective: {objective}
- Teacher's prompt: {prompt}
- Grade: {grade}    Subject: {subject}
- WIDA proficiency range: {wida_min}-{wida_max}
- WIDA Key Language Use: {klu}   (Narrate | Inform | Explain | Argue)
- Time budget: EXACTLY {time_minutes} minutes (45 or 90)

REQUIREMENTS (non-negotiable)
1. Write a Content objective AND a Language objective (Dual-Objective).
2. Segment timings must sum to exactly {time_minutes}, allocated:
   - 45 min  -> Preparing 10, Interacting 25, Extending 10
   - 90 min  -> Preparing 15, Interacting 55, Extending 20
3. EXACTLY THREE discussion pieces, one per moment. Choose protocols
   from this palette and do not repeat the same protocol three times:
     Turn-and-Talk (floor)
     Discussion Move Cards (Probe / Paraphrase / Build / Challenge / Clarify)
     Stronger & Clearer Each Time
     Anticipatory Guide discussion
     Write-Converse-Write
     Source Triangulation
     Visual-First Reading
     Quick-Writes by Level
     Jigsaw  (90-min only)
4. For each discussion piece, provide:
   - Protocol name (and a link to its teaching_tools/*.html companion).
   - Open, content-anchored prompt.
   - Sentence stems for EVERY WIDA level in the requested range.
   - Which Discussion Move Cards students must use.
   - Timing within the moment.
   - Teacher move (what to listen for; when to cold-call).
5. Apply Gradual Release across the moments (model -> guided -> independent).
6. Insert a formative check at each moment transition; name what to
   look or listen for.
7. End with an Exit Ticket Differentiator: one prompt per WIDA level
   in the range.
8. Cite the framework only when it clarifies (WIDA, SIOP, Zwiers, QTEL).

OUTPUT FORMAT (Markdown, exact section order)

# {{Title}}
## Objectives
- Content: ...
- Language: ...  (KLU: {klu})
## Standard
## Materials
## Lesson Arc
### Preparing ({pre} min)
Teacher does / Students do / Formative check
#### Discussion 1 — <Protocol> ({d1} min)
- Prompt:
- Stems (WIDA k): ...   (one bullet per level in range)
- Move cards in play:
- Teacher move:
- Companion tool: [name](/teaching_tools/...html)
### Interacting ({inter} min)
... (same shape, Discussion 2)
### Extending ({ext} min)
... (same shape, Discussion 3)
## Differentiation
- Newcomer (WIDA 1) supports
- Extension for emerging mastery
## Assessment
- Formative checkpoints (3, one per moment)
- Exit ticket (one prompt per WIDA level in range)
- Companion rubric: [Dual-Lens Rubric](/teaching_tools/co-teaching/19-dual-lens-rubric.html)

STYLE
- Specific named routines, never generic strategies.
- Design at the proficiency-level grain. No student PII.
"""
```

## Acceptance checks (server-side, before returning)
- Three `#### Discussion \\d+` headings present.
- Segment minutes parse and sum to `timeMinutes` (±0).
- Each discussion segment names a protocol from the palette and has
  stems for every level in `[wida_min, wida_max]`.
- At least two distinct protocols across the three pieces.
- Exit ticket has one prompt per WIDA level in range.
- On failure: retry once with a corrective system message listing the
  specific violations; if still failing, return the draft with a warning
  banner so the teacher can edit.

## Files to add or change
- `prompts.py` — add `LESSON_PLAN_SYSTEM_PROMPT`, plus a small
  `LESSON_VALIDATION_FEEDBACK_PROMPT` for the retry path.
- `dashboard_server.py` — add `POST /api/lesson` (streamed) and a
  static handler for `/teaching_tools/*`.
- `dashboard/app.js` — add `PlanLesson` view + nav entry.
- `dashboard/styles.css` — discussion-piece card styles matching the
  teaching_tools aesthetic (DM Sans, `#1a1a2e`).
- `tests/test_dashboard_server.py` — validation, FERPA, retry path.

## Open items
- KLU input: surface as a dropdown or infer from `objective`? (Recommend
  explicit dropdown — teachers will want control.)
- Should saved lessons embed the companion-tool links as part of the
  saved markdown? (Recommend yes — printable + portable.)
- Streaming: stdlib `http.server` can do chunked transfer but not true
  SSE EventSource semantics. The client can still consume the chunked
  body via `response.body.getReader()`. Acceptable trade for keeping
  the stack dependency-free.
