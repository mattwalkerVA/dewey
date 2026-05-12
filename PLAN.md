# Plan: Browser-loaded Dewey — React Lesson Planner

## Goal
Turn Dewey from a Python CLI into a browser app where a teacher enters
**standard + learning objective + prompt + grade + subject + WIDA range + 45/90 min**
and gets back a detailed, research-grounded lesson with **exactly three student
discussion pieces** (Turn-and-Talk is the floor, stronger protocols preferred).

## Architecture (per design decisions)
- **Backend**: FastAPI wrapper around the existing `agent.py`, `memory.py`,
  `tools/` modules. Stateless service; Anthropic key stays server-side.
- **Frontend**: React + Vite + TypeScript + Tailwind.
- **Memory**: Browser-owned. Teacher profile in `localStorage`; saved lessons
  + retrieval index in IndexedDB (via `idb-keyval` or Dexie). Profile is sent
  up with each request so the server stays stateless.
- **FERPA filter**: keep server-side as defense in depth; surface "PII
  removed" banner in UI when the filter fires.

```
web/  ──HTTP/SSE──>  api/  ──>  Anthropic
  IndexedDB                  reuses tools/, prompts.py, FERPA filter
```

## Input contract (form schema)
| Field | Type | Notes |
|---|---|---|
| `standard` | string | autosuggest backed by `tools/standards.py` |
| `objective` | string | learning objective (free text) |
| `prompt` | string | teacher's specific ask / context |
| `grade` | enum K–12 | one value |
| `subject` | string | ELA, Math, Science, Social Studies, etc. |
| `widaLevels` | [min, max] 1–6 | range slider |
| `timeMinutes` | 45 \| 90 | toggle, exact two values |

## Output contract (lesson plan schema)
A structured plan that **must** contain:

- **Content objective** + **Language objective** (SIOP)
- **Standard(s) addressed**
- **Materials**
- **Sequence** with timing that sums to `timeMinutes`:
  - 45-min skeleton: Hook (5) → Mini-lesson (10) → **Discussion 1** (5–7) →
    Guided practice (8) → **Discussion 2** (5) → Independent practice (8) →
    **Discussion 3 / synthesis** (4) → Exit ticket (3)
  - 90-min skeleton: same shape with one extended protocol (e.g., Socratic
    Seminar or Jigsaw as Discussion 2 or 3) and a longer independent block.
- **Differentiation by WIDA level** (sentence frames at each level in range)
- **Formative assessment checkpoints** (what to look/listen for)
- **Exit ticket** (3 questions or prompt)

### Each discussion piece must include
1. **Protocol name** — Turn-and-Talk minimum. Preferred richer protocols:
   Think–Pair–Share, Stronger & Clearer Each Time (Zwiers), 4 A's Text Protocol,
   Save the Last Word, Talking Chips, Numbered Heads Together, Jigsaw,
   Socratic Seminar, Chalk Talk, Concentric Circles.
2. **Prompt / question** (open, productive, content-anchored).
3. **Sentence stems** keyed to each WIDA level in the requested range.
4. **Timing** (and how teacher signals end).
5. **Teacher move** — what to listen for, when to cold-call, how to redirect.
6. **Accountable talk move** — how students build on / push back on each other.

## Teaching tactics to bake into the system prompt
- Gradual Release of Responsibility (I do / We do / You do)
- Comprehensible input (visuals, realia, gestures, cognates)
- Productive struggle + scaffolds you can fade
- Wait time (≥5s) and cold-call with thinking time
- Show Call / Right is Right / Stretch It (Lemov)
- Total Physical Response for newcomers
- Culturally sustaining text/example choice
- Zwiers' four academic-language skills: elaboration, fortification,
  persuasion, negotiation — at least one is exercised in the lesson
- Formative checks every transition; never end a phase without a quick check

## Implementation phases

### Phase 0 — Scaffolding
- Add `web/` (Vite + React + TS + Tailwind).
- Add `api/` for FastAPI.
- Update `requirements.txt`: `fastapi`, `uvicorn[standard]`, `sse-starlette`,
  `pydantic`.

### Phase 1 — Backend API
- `api/main.py`: FastAPI app, CORS for the Vite dev origin.
- `api/lesson.py`:
  - `POST /api/lesson` — body matches input contract. Streams SSE chunks.
  - Validates with Pydantic. Applies FERPA filter to free-text fields.
  - Calls Anthropic with the new `LESSON_PLAN_SYSTEM_PROMPT` (below).
  - Uses existing `tools/standards.py` if `standard` is fuzzy.
- `api/standards.py`: `GET /api/standards?q=…` for the autosuggest input.
- `prompts.py`: add `LESSON_PLAN_SYSTEM_PROMPT` (see template below).
- Schema validation on the way out: server parses the JSON header the model
  emits and rejects/retries if `discussion_pieces.length != 3` or timing
  doesn't sum to `timeMinutes`.

### Phase 2 — React frontend
Components:
- `LessonInputForm` — all seven fields, client-side validation.
- `StandardPicker` — debounced autosuggest hitting `/api/standards`.
- `WidaRangeSlider` — dual-thumb 1–6.
- `TimeToggle` — segmented control, 45 / 90.
- `LessonPlanView` — renders the streamed plan as it arrives.
- `DiscussionPieceCard` — protocol name, stems by WIDA level, teacher moves.
- `SavedLessonsDrawer` — list from IndexedDB; click to reload into the view.
- `TeacherProfileSheet` — name, grade(s), subject(s), default WIDA range;
  persisted to `localStorage`, sent up with each request.
- `PiiBanner` — shown when server returns the FERPA-modified flag.

State / data:
- `web/src/lib/db.ts` — IndexedDB wrapper (`saveLesson`, `listLessons`,
  `searchLessons`).
- `web/src/lib/api.ts` — fetch + SSE parser.

### Phase 3 — Polish
- Print stylesheet (`@media print`) — discussion cards collapse cleanly.
- Copy-as-markdown + download `.md` for each saved lesson.
- Empty states with examples teachers can click to fill the form.
- Loading skeleton that mirrors the lesson skeleton so the streamed output
  feels grounded.

### Phase 4 — Cutover
- Keep `agent.py` CLI working (it uses the same `prompts.py` / `tools/`).
- README: split into "CLI" and "Web" sections; document `uvicorn api.main:app`
  and `npm run dev` from `web/`.

## Draft `LESSON_PLAN_SYSTEM_PROMPT`

```python
LESSON_PLAN_SYSTEM_PROMPT = """\
You are Dewey, designing a single class-period lesson for a K-12 teacher.

INPUT
- Standard: {standard}
- Learning objective: {objective}
- Teacher's prompt / context: {prompt}
- Grade: {grade}
- Subject: {subject}
- WIDA proficiency range: {wida_min}-{wida_max}
- Time budget: EXACTLY {time_minutes} minutes

REQUIREMENTS (non-negotiable)
1. Produce ONE content objective AND ONE language objective (SIOP).
2. The sequence's segment timings MUST sum to exactly {time_minutes}.
3. Include EXACTLY THREE student discussion pieces, spread across the lesson:
   one early (activate / surface thinking), one middle (deepen / push back),
   one late (synthesize / transfer).
4. Each discussion piece uses a NAMED protocol. Turn-and-Talk is acceptable
   as a floor; prefer richer protocols when the time and content support it
   (Think-Pair-Share, Stronger & Clearer Each Time, 4 A's, Save the Last Word,
   Talking Chips, Numbered Heads Together, Jigsaw, Socratic Seminar,
   Chalk Talk, Concentric Circles). Do not repeat the same protocol for all
   three pieces.
5. For each discussion piece, provide sentence stems for EACH WIDA level in
   the requested range (e.g., if range is 2-4, provide stems for 2, 3, and 4).
6. Apply Gradual Release of Responsibility across the lesson.
7. Insert a formative check at every transition; name what the teacher
   should look or listen for.
8. End with a 3-prompt exit ticket aligned to the objectives.

OUTPUT FORMAT
Return Markdown with this exact section order:

# {{Title}}
## Objectives
- Content: ...
- Language: ...
## Standard(s)
## Materials
## Sequence
For each segment, use a level-3 heading like:
### 1. Hook — Activate prior knowledge (5 min)
Body: what the teacher does, what students do, formative check.
For discussion segments, use this sub-structure:
### 3. Discussion 1 — <Protocol name> (X min)
- Prompt:
- Stems (WIDA 2):
- Stems (WIDA 3):
- Stems (WIDA 4):
- Teacher move:
- Accountable-talk move:
## Differentiation
- Newcomer (WIDA 1) supports
- Reaching mastery / extension
## Assessment
- Formative checkpoints (list)
- Exit ticket (3 prompts)

STYLE
- Be specific. Name routines, not generic strategies.
- Cite the framework when it clarifies (SIOP, WIDA, Zwiers, QTEL).
- No student PII; design at the proficiency-level grain.
"""
```

## Acceptance checks (run server-side before returning)
- Regex / parser confirms three `### \\d+\\. Discussion` segments.
- All segment minutes sum to `timeMinutes` (±0).
- Each discussion segment names a protocol and has stems for every level in
  the requested WIDA range.
- If any check fails, retry once with a corrective system message before
  surfacing an error.

## Open items
- **mattwalker.education**: the site returns 403 to programmatic fetches, so
  I couldn't pull the component vocabulary directly. If there's a specific
  set of named components / tactics from the site you want enforced, paste
  the list and I'll fold it into the system prompt + the
  `DiscussionPieceCard` rendering.
- Default standards corpus (CCSS? NGSS? state-specific)? Affects what
  `tools/standards.py` indexes.
- Auth: single-teacher local install, or shared deploy?
