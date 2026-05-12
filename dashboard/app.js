import React, { useEffect, useMemo, useRef, useState } from "https://esm.sh/react@18.3.1";
import { createRoot } from "https://esm.sh/react-dom@18.3.1/client";
import htm from "https://esm.sh/htm@3.1.1";
import { Marked } from "https://esm.sh/marked@13.0.3";
import DOMPurify from "https://esm.sh/dompurify@3.1.6";

import {
  applyRedactions,
  detectPersons,
  getBackendLabel,
  isLoaded as piiIsLoaded,
  loadPiiAssist,
  onProgress as onPiiProgress,
} from "./pii.js";

const markdownRenderer = new Marked({ gfm: true, breaks: false });

function renderMarkdown(markdown) {
  if (!markdown) return "";
  return DOMPurify.sanitize(markdownRenderer.parse(markdown), {
    ADD_ATTR: ["target"],
  });
}

const COMPANION_LINK_RE = /\[([^\]\n]+)\]\((\/teaching_tools\/[^)]+\.html)\)/g;

function extractCompanionTools(markdown) {
  if (!markdown) return [];
  const seen = new Map();
  for (const match of markdown.matchAll(COMPANION_LINK_RE)) {
    const [, name, path] = match;
    if (!seen.has(path)) seen.set(path, name.trim());
  }
  return [...seen.entries()].map(([path, name]) => ({ name, path }));
}

const DEMO_PROMPTS = [
  {
    label: "5th ELA · inference & setting · 45 min",
    form: {
      standard: "5.5 — Reading: fictional texts and narrative nonfiction",
      objective:
        "Students will infer how the setting in chapter 3 shapes the protagonist's choices, citing two pieces of textual evidence.",
      prompt:
        "We're three chapters into our anchor novel. Most of my newcomers need visual scaffolds; the rest of the class is at WIDA 3–4. Focus on text evidence.",
      grade: "5",
      subject: "ELA",
      klu: "Explain",
      widaMin: 2,
      widaMax: 4,
      timeMinutes: 45,
    },
  },
  {
    label: "8th Science · ecosystems argument · 90 min",
    form: {
      standard: "LS.9 — Interactions of living systems",
      objective:
        "Students will construct an argument about how a specific human activity has impacted a local ecosystem, supporting the claim with two pieces of evidence and addressing one counterclaim.",
      prompt:
        "Co-taught block. Three newcomers (WIDA 1–2), about half the class at WIDA 3–4. Use the Chesapeake Bay as our anchor case study.",
      grade: "8",
      subject: "Science",
      klu: "Argue",
      widaMin: 1,
      widaMax: 4,
      timeMinutes: 90,
    },
  },
  {
    label: "3rd Math · unit fractions · 45 min",
    form: {
      standard: "3.2 — Fractions",
      objective:
        "Students will represent unit fractions on a number line and compare two unit fractions with the same denominator using a visual model.",
      prompt:
        "Introducing number-line fractions for the first time. About a third of my students are Spanish-dominant at WIDA 2–3 and are strong with visual representations.",
      grade: "3",
      subject: "Math",
      klu: "Inform",
      widaMin: 2,
      widaMax: 3,
      timeMinutes: 45,
    },
  },
];

const html = htm.bind(React.createElement);

const views = [
  ["plan", "Plan Lesson"],
  ["library", "Lesson Library"],
  ["profile", "Teacher Profile"],
  ["standards", "Standards"],
  ["save", "Save Plan"],
];

const PII_STORAGE_KEY = "dewey:piiAssist:enabled";

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.error || payload.errors?.join("; ") || "Request failed.");
  }
  return payload;
}

function Empty({ children }) {
  return html`<div className="empty">${children}</div>`;
}

// --- PII Assist ---------------------------------------------------------

function usePiiAssist() {
  const [enabled, setEnabledState] = useState(() => {
    try {
      return localStorage.getItem(PII_STORAGE_KEY) === "1";
    } catch {
      return false;
    }
  });
  const [status, setStatus] = useState(piiIsLoaded() ? "ready" : "idle");
  const [progress, setProgress] = useState(null);
  const [backend, setBackend] = useState(getBackendLabel());
  const [error, setError] = useState(null);

  useEffect(() => {
    const off = onPiiProgress((event) => {
      if (event.status === "progress" && typeof event.progress === "number") {
        setProgress(Math.round(event.progress));
      }
      if (event.status === "loading-library") setStatus("loading-library");
      if (event.status === "loading-model") setStatus("loading-model");
      if (event.status === "ready") {
        setStatus("ready");
        setProgress(null);
        setBackend(getBackendLabel());
      }
      if (event.status === "error") {
        setStatus("error");
        setError(event.message || "Failed to load PII assist.");
      }
    });
    return off;
  }, []);

  useEffect(() => {
    try {
      localStorage.setItem(PII_STORAGE_KEY, enabled ? "1" : "0");
    } catch {
      /* localStorage not available */
    }
    if (enabled && !piiIsLoaded()) {
      setStatus("loading-library");
      setError(null);
      loadPiiAssist().catch((err) => {
        console.error(err);
        setError(String(err));
      });
    }
  }, [enabled]);

  return {
    enabled,
    setEnabled: setEnabledState,
    status,
    progress,
    backend,
    error,
  };
}

function PiiAssistToggle({ assist }) {
  function toggle() {
    if (!assist.enabled) {
      const ok = window.confirm(
        "Download the local PII model (~80 MB)?\n\n" +
          "It runs entirely in your browser — no text leaves this tab. " +
          "Cached for next time.",
      );
      if (!ok) return;
    }
    assist.setEnabled(!assist.enabled);
  }

  let badge = "Off";
  let badgeClass = "off";
  if (assist.enabled) {
    if (assist.status === "ready") {
      badge = assist.backend;
      badgeClass = "ready";
    } else if (assist.status === "error") {
      badge = "Failed";
      badgeClass = "error";
    } else if (assist.progress != null) {
      badge = `Loading ${assist.progress}%`;
      badgeClass = "loading";
    } else {
      badge = "Loading…";
      badgeClass = "loading";
    }
  }

  return html`
    <div className="pii-toggle">
      <label className="pii-switch">
        <input type="checkbox" checked=${assist.enabled} onChange=${toggle} />
        <span className="pii-switch-track" aria-hidden="true"></span>
        <span className="pii-switch-label">Local PII assist</span>
      </label>
      <span className=${`pii-badge ${badgeClass}`}>${badge}</span>
      ${assist.error ? html`<span className="pii-error">${assist.error}</span>` : null}
    </div>
  `;
}

function useDetectedPersons(value, assist) {
  const [spans, setSpans] = useState([]);
  const lastRunRef = useRef(0);
  const runIdRef = useRef(0);

  useEffect(() => {
    if (!assist.enabled || assist.status !== "ready") {
      setSpans([]);
      return undefined;
    }
    if (!value || !value.trim()) {
      setSpans([]);
      return undefined;
    }
    const id = ++runIdRef.current;
    const handle = setTimeout(async () => {
      lastRunRef.current = id;
      try {
        const detected = await detectPersons(value);
        if (id === runIdRef.current) setSpans(detected);
      } catch (error) {
        console.error("PII detection failed:", error);
      }
    }, 350);
    return () => clearTimeout(handle);
  }, [value, assist.enabled, assist.status]);

  return spans;
}

function PiiReview({ spans, accepted, setAccepted }) {
  if (!spans.length) return null;

  function toggleKey(key) {
    setAccepted((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  return html`
    <div className="pii-review">
      <div className="pii-review-header">
        <strong>Local PII assist found ${spans.length} name${spans.length === 1 ? "" : "s"}.</strong>
        <span>Tap each one to redact it before submitting.</span>
      </div>
      <div className="pii-chips">
        ${spans.map((span) => {
          const key = `${span.start}:${span.end}`;
          const isAccepted = accepted.has(key);
          return html`
            <button
              type="button"
              key=${key}
              className=${`pii-chip ${isAccepted ? "accepted" : ""}`}
              onClick=${() => toggleKey(key)}
              title="Click to ${isAccepted ? "keep" : "redact"} this name"
            >
              ${isAccepted ? "Redacted: " : ""}${span.text}
            </button>
          `;
        })}
      </div>
    </div>
  `;
}

// --- Plan Lesson view ---------------------------------------------------

const SUBJECTS = ["ELA", "Math", "Science", "Social Studies", "Other"];
const GRADES = ["K", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12"];
const KLUS = ["Narrate", "Inform", "Explain", "Argue"];

const DEFAULT_FORM = {
  standard: "",
  objective: "",
  prompt: "",
  grade: "5",
  subject: "ELA",
  klu: "Explain",
  widaMin: 2,
  widaMax: 4,
  timeMinutes: 45,
};

async function* streamLesson(body) {
  const response = await fetch("/api/lesson", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload.errors?.join("; ") || payload.error || `HTTP ${response.status}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    let separator;
    while ((separator = buffer.indexOf("\n\n")) !== -1) {
      const frame = buffer.slice(0, separator);
      buffer = buffer.slice(separator + 2);
      let eventName = "message";
      let dataLines = [];
      for (const line of frame.split("\n")) {
        if (line.startsWith("event: ")) eventName = line.slice(7).trim();
        else if (line.startsWith("data: ")) dataLines.push(line.slice(6));
      }
      if (!dataLines.length) continue;
      let data;
      try {
        data = JSON.parse(dataLines.join("\n"));
      } catch {
        data = dataLines.join("\n");
      }
      yield { event: eventName, data };
    }
  }
}

function StandardField({ value, onChange }) {
  const [results, setResults] = useState([]);
  const [open, setOpen] = useState(false);
  const debounceRef = useRef(null);

  function handleChange(next) {
    onChange(next);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    if (!next.trim()) {
      setResults([]);
      return;
    }
    debounceRef.current = setTimeout(async () => {
      try {
        const payload = await api(`/api/standards?query=${encodeURIComponent(next)}`);
        setResults(payload.items.slice(0, 5));
        setOpen(true);
      } catch (error) {
        console.error(error);
      }
    }, 250);
  }

  return html`
    <label className="standard-field">
      Standard
      <input
        value=${value}
        onChange=${(event) => handleChange(event.target.value)}
        onFocus=${() => setOpen(true)}
        onBlur=${() => setTimeout(() => setOpen(false), 150)}
        placeholder="SOL code or keyword (e.g. 5.4, inference)"
      />
      ${open && results.length > 0
        ? html`
            <ul className="standard-suggestions">
              ${results.map(
                (result) => html`
                  <li
                    key=${result.code}
                    onMouseDown=${() => {
                      onChange(`${result.code} — ${result.strand}`);
                      setOpen(false);
                    }}
                  >
                    <strong>${result.code}</strong>
                    <span>${result.strand}</span>
                  </li>
                `,
              )}
            </ul>
          `
        : null}
    </label>
  `;
}

function WidaRange({ min, max, setMin, setMax }) {
  function adjust(field, value) {
    const n = parseInt(value, 10);
    if (Number.isNaN(n)) return;
    if (field === "min") setMin(Math.min(n, max));
    else setMax(Math.max(n, min));
  }

  return html`
    <fieldset className="wida-range">
      <legend>WIDA proficiency range</legend>
      <label>
        Min
        <select value=${min} onChange=${(event) => adjust("min", event.target.value)}>
          ${[1, 2, 3, 4, 5, 6].map((n) => html`<option key=${n} value=${n}>${n}</option>`)}
        </select>
      </label>
      <label>
        Max
        <select value=${max} onChange=${(event) => adjust("max", event.target.value)}>
          ${[1, 2, 3, 4, 5, 6].map((n) => html`<option key=${n} value=${n}>${n}</option>`)}
        </select>
      </label>
      <span className="wida-range-summary">Stems for levels ${min}–${max}.</span>
    </fieldset>
  `;
}

function TimeToggle({ value, onChange }) {
  return html`
    <fieldset className="time-toggle">
      <legend>Time budget</legend>
      ${[45, 90].map(
        (minutes) => html`
          <label key=${minutes} className=${value === minutes ? "active" : ""}>
            <input
              type="radio"
              name="time"
              value=${minutes}
              checked=${value === minutes}
              onChange=${() => onChange(minutes)}
            />
            ${minutes} min
          </label>
        `,
      )}
    </fieldset>
  `;
}

function CompanionTools({ tools }) {
  if (!tools.length) return null;
  return html`
    <section className="panel companion-tools">
      <h3>Companion tools</h3>
      <p className="companion-blurb">Printable cards from this lesson — open each in a new tab to assign or print.</p>
      <div className="companion-grid">
        ${tools.map(
          (tool) => html`
            <a
              key=${tool.path}
              className="companion-card"
              href=${tool.path}
              target="_blank"
              rel="noopener noreferrer"
            >
              <span className="companion-name">${tool.name}</span>
              <span className="companion-path">${tool.path.replace("/teaching_tools/", "")}</span>
            </a>
          `,
        )}
      </div>
    </section>
  `;
}

function DemoPrompts({ onPick }) {
  return html`
    <div className="demo-prompts">
      <p>Submit the form to draft a lesson, or load a sample:</p>
      <div className="demo-prompt-grid">
        ${DEMO_PROMPTS.map(
          (preset) => html`
            <button
              key=${preset.label}
              type="button"
              className="demo-prompt"
              onClick=${() => onPick(preset.form)}
            >
              ${preset.label}
            </button>
          `,
        )}
      </div>
    </div>
  `;
}

function LessonStream({ events, markdown, violations, status, onPickDemo, isStreaming }) {
  const renderedHtml = useMemo(() => renderMarkdown(markdown), [markdown]);
  const showTypingCursor = isStreaming && markdown;

  return html`
    <section className="panel lesson-stream">
      <div className="lesson-stream-header">
        <h3>Lesson draft</h3>
        <span className=${`stream-status ${status}`}>${status}</span>
      </div>
      ${events
        .filter((event) => event.event === "notice")
        .map((event, index) => html`<div key=${index} className="stream-notice">${event.data.text}</div>`)}
      ${violations.length > 0
        ? html`
            <div className="violations">
              <strong>Contract violations:</strong>
              <ul>
                ${violations.map((v, index) => html`<li key=${index}>${v}</li>`)}
              </ul>
            </div>
          `
        : null}
      ${markdown
        ? html`
            <article
              className=${`lesson-rendered ${showTypingCursor ? "streaming" : ""}`}
              dangerouslySetInnerHTML=${{ __html: renderedHtml }}
            ></article>
          `
        : html`
            <${Empty}>
              <${DemoPrompts} onPick=${onPickDemo} />
            <//>
          `}
    </section>
  `;
}

function PlanLesson({ setStatus, assist }) {
  const [form, setForm] = useState(DEFAULT_FORM);
  const [accepted, setAccepted] = useState(new Set());
  const [events, setEvents] = useState([]);
  const [markdown, setMarkdown] = useState("");
  const [violations, setViolations] = useState([]);
  const [streamStatus, setStreamStatus] = useState("idle");
  const [saveTitle, setSaveTitle] = useState("");

  const objectiveSpans = useDetectedPersons(form.objective, assist);
  const promptSpans = useDetectedPersons(form.prompt, assist);

  function update(field, value) {
    setForm((current) => ({ ...current, [field]: value }));
  }

  async function submit(event) {
    event.preventDefault();
    setEvents([]);
    setMarkdown("");
    setViolations([]);
    setStreamStatus("streaming");

    const payload = {
      standard: form.standard,
      objective: applyRedactions(form.objective, objectiveSpans, accepted),
      prompt: applyRedactions(form.prompt, promptSpans, accepted),
      grade: form.grade,
      subject: form.subject,
      klu: form.klu,
      timeMinutes: form.timeMinutes,
      widaLevels: [form.widaMin, form.widaMax],
    };

    try {
      for await (const event of streamLesson(payload)) {
        setEvents((prev) => [...prev, event]);
        if (event.event === "chunk") {
          setMarkdown((prev) => prev + event.data.text);
        } else if (event.event === "done") {
          setMarkdown(event.data.markdown);
          setViolations(event.data.violations || []);
          setStreamStatus(event.data.violations?.length ? "done-with-warnings" : "done");
          setStatus(
            event.data.violations?.length
              ? `Draft complete with ${event.data.violations.length} contract issue(s).`
              : "Draft complete.",
          );
        } else if (event.event === "error") {
          setStreamStatus("error");
          setStatus(`Generation failed: ${event.data.message}`);
        } else if (event.event === "notice") {
          setStatus(event.data.text);
          if (event.data.text?.toLowerCase().includes("retry")) {
            setMarkdown("");
          }
        }
      }
    } catch (error) {
      setStreamStatus("error");
      setStatus(`Request failed: ${error.message}`);
    }
  }

  async function saveToLibrary() {
    if (!markdown) return;
    const title = saveTitle.trim() || form.objective.split(/[.\n]/)[0].slice(0, 60) || "Untitled Lesson";
    try {
      await api("/api/plans", {
        method: "POST",
        body: JSON.stringify({
          title,
          grade: form.grade,
          subject: form.subject,
          content: markdown,
        }),
      });
      setStatus(`Saved "${title}" to the library.`);
    } catch (error) {
      setStatus(`Save failed: ${error.message}`);
    }
  }

  const piiSpans = useMemo(
    () => [...objectiveSpans, ...promptSpans],
    [objectiveSpans, promptSpans],
  );

  const companionTools = useMemo(() => extractCompanionTools(markdown), [markdown]);

  function loadDemoForm(preset) {
    setForm(preset);
    setAccepted(new Set());
    setMarkdown("");
    setEvents([]);
    setViolations([]);
    setStreamStatus("idle");
  }

  return html`
    <section className="plan-grid">
      <form className="panel form plan-form" onSubmit=${submit}>
        <h3>Plan a lesson</h3>
        <${StandardField}
          value=${form.standard}
          onChange=${(value) => update("standard", value)}
        />
        <label>
          Learning objective
          <textarea
            value=${form.objective}
            onChange=${(event) => update("objective", event.target.value)}
            placeholder="Students will explain how setting shapes mood..."
            rows=${2}
            required
          ></textarea>
        </label>
        <label>
          Teacher prompt / context
          <textarea
            value=${form.prompt}
            onChange=${(event) => update("prompt", event.target.value)}
            placeholder="Anything Dewey should know: anchor text, time of year, prior lessons, student strengths..."
            rows=${3}
          ></textarea>
        </label>
        <${PiiReview} spans=${piiSpans} accepted=${accepted} setAccepted=${setAccepted} />
        <div className="form-row">
          <label>
            Grade
            <select value=${form.grade} onChange=${(event) => update("grade", event.target.value)}>
              ${GRADES.map((grade) => html`<option key=${grade} value=${grade}>${grade}</option>`)}
            </select>
          </label>
          <label>
            Subject
            <select value=${form.subject} onChange=${(event) => update("subject", event.target.value)}>
              ${SUBJECTS.map((subject) => html`<option key=${subject} value=${subject}>${subject}</option>`)}
            </select>
          </label>
          <label>
            KLU
            <select value=${form.klu} onChange=${(event) => update("klu", event.target.value)}>
              ${KLUS.map((klu) => html`<option key=${klu} value=${klu}>${klu}</option>`)}
            </select>
          </label>
        </div>
        <${WidaRange}
          min=${form.widaMin}
          max=${form.widaMax}
          setMin=${(value) => update("widaMin", value)}
          setMax=${(value) => update("widaMax", value)}
        />
        <${TimeToggle} value=${form.timeMinutes} onChange=${(value) => update("timeMinutes", value)} />
        <button className="primary" type="submit" disabled=${streamStatus === "streaming"}>
          ${streamStatus === "streaming" ? "Drafting…" : "Draft lesson"}
        </button>
      </form>
      <div className="plan-output">
        <${LessonStream}
          events=${events}
          markdown=${markdown}
          violations=${violations}
          status=${streamStatus}
          onPickDemo=${loadDemoForm}
          isStreaming=${streamStatus === "streaming"}
        />
        ${markdown
          ? html`
              <section className="panel save-row">
                <input
                  className="save-title"
                  value=${saveTitle}
                  onChange=${(event) => setSaveTitle(event.target.value)}
                  placeholder="Lesson title (defaults to first line of objective)"
                />
                <button
                  className="primary"
                  type="button"
                  onClick=${saveToLibrary}
                  disabled=${streamStatus === "streaming"}
                >
                  Save to library
                </button>
              </section>
            `
          : null}
        <${CompanionTools} tools=${companionTools} />
      </div>
    </section>
  `;
}

// --- Existing views (unchanged behavior) --------------------------------

function LessonLibrary({ setStatus }) {
  const [plans, setPlans] = useState([]);

  async function loadPlans() {
    const payload = await api("/api/plans");
    setPlans(payload.items);
    setStatus(`Loaded ${payload.items.length} saved plan${payload.items.length === 1 ? "" : "s"}.`);
  }

  useEffect(() => {
    loadPlans().catch((error) => setStatus(error.message));
  }, []);

  return html`
    <section>
      <div className="toolbar">
        <button onClick=${loadPlans}>Refresh</button>
      </div>
      ${plans.length === 0
        ? html`<${Empty}>No saved lesson plans yet.<//>`
        : html`
            <div className="list">
              ${plans.map(
                (plan) => html`
                  <article className="item" key=${plan.path}>
                    <h4>${plan.title}</h4>
                    <p>${plan.filename}</p>
                    <div className="meta">
                      ${plan.grade ? html`<span className="tag">Grade ${plan.grade}</span>` : null}
                      ${plan.subject ? html`<span className="tag">${plan.subject}</span>` : null}
                      <span className="tag">${new Date(plan.modified).toLocaleString()}</span>
                    </div>
                  </article>
                `,
              )}
            </div>
          `}
    </section>
  `;
}

function Profile({ setStatus }) {
  const [items, setItems] = useState([]);

  async function loadProfile() {
    const payload = await api("/api/profile");
    setItems(payload.items);
    setStatus(`Loaded ${payload.items.length} profile note${payload.items.length === 1 ? "" : "s"}.`);
  }

  async function clearProfile() {
    const payload = await api("/api/profile", { method: "DELETE" });
    setItems([]);
    setStatus(`Deleted ${payload.deleted} profile note${payload.deleted === 1 ? "" : "s"}.`);
  }

  useEffect(() => {
    loadProfile().catch((error) => setStatus(error.message));
  }, []);

  return html`
    <section>
      <div className="toolbar">
        <button onClick=${loadProfile}>Refresh</button>
        <button className="danger" onClick=${clearProfile}>Clear Profile</button>
      </div>
      ${items.length === 0
        ? html`<${Empty}>No teacher profile notes saved.<//>`
        : html`
            <div className="list">
              ${items.map(
                (item) => html`
                  <article className="item" key=${item.id}>
                    <p>${item.content}</p>
                    <div className="meta">
                      ${item.category ? html`<span className="tag">${item.category}</span>` : null}
                    </div>
                  </article>
                `,
              )}
            </div>
          `}
    </section>
  `;
}

function Standards({ setStatus }) {
  const [mode, setMode] = useState("sol");
  const [query, setQuery] = useState("");
  const [subject, setSubject] = useState("");
  const [grade, setGrade] = useState("");
  const [level, setLevel] = useState("0");
  const [domain, setDomain] = useState("");
  const [results, setResults] = useState([]);

  async function search(event) {
    event.preventDefault();
    const path =
      mode === "sol"
        ? `/api/standards?query=${encodeURIComponent(query)}&subject=${encodeURIComponent(subject)}&grade=${encodeURIComponent(grade)}`
        : `/api/wida?level=${encodeURIComponent(level)}&domain=${encodeURIComponent(domain)}`;
    const payload = await api(path);
    setResults(payload.items);
    setStatus(`Found ${payload.items.length} result${payload.items.length === 1 ? "" : "s"}.`);
  }

  return html`
    <section className="grid">
      <form className="panel form" onSubmit=${search}>
        <h3>${mode === "sol" ? "Virginia SOL Search" : "WIDA Descriptor Search"}</h3>
        <label>
          Source
          <select value=${mode} onChange=${(event) => setMode(event.target.value)}>
            <option value="sol">Virginia SOLs</option>
            <option value="wida">WIDA</option>
          </select>
        </label>
        ${mode === "sol"
          ? html`
              <label>
                Keywords
                <input
                  value=${query}
                  onChange=${(event) => setQuery(event.target.value)}
                  placeholder="fractions, inference, ecosystems"
                />
              </label>
              <div className="form-row">
                <label>
                  Subject
                  <input value=${subject} onChange=${(event) => setSubject(event.target.value)} placeholder="Math" />
                </label>
                <label>
                  Grade
                  <input value=${grade} onChange=${(event) => setGrade(event.target.value)} placeholder="4" />
                </label>
              </div>
            `
          : html`
              <div className="form-row">
                <label>
                  Level
                  <select value=${level} onChange=${(event) => setLevel(event.target.value)}>
                    <option value="0">All levels</option>
                    <option value="1">Level 1</option>
                    <option value="2">Level 2</option>
                    <option value="3">Level 3</option>
                    <option value="4">Level 4</option>
                    <option value="5">Level 5</option>
                    <option value="6">Level 6</option>
                  </select>
                </label>
                <label>
                  Domain
                  <select value=${domain} onChange=${(event) => setDomain(event.target.value)}>
                    <option value="">All domains</option>
                    <option value="Listening">Listening</option>
                    <option value="Speaking">Speaking</option>
                    <option value="Reading">Reading</option>
                    <option value="Writing">Writing</option>
                  </select>
                </label>
              </div>
            `}
        <button className="primary" type="submit">Search</button>
      </form>
      <section className="panel">
        <h3>Results</h3>
        ${results.length === 0
          ? html`<${Empty}>No results loaded.<//>`
          : html`
              <div className="list">
                ${results.map(
                  (result, index) => html`
                    <article className="item" key=${`${result.code || result.domain}-${index}`}>
                      <h4>${result.code || `Level ${result.level} ${result.domain}`}</h4>
                      <p>${result.text || result.descriptor}</p>
                      <div className="meta">
                        ${result.subject ? html`<span className="tag">${result.subject}</span>` : null}
                        ${result.grade ? html`<span className="tag">Grade ${result.grade}</span>` : null}
                        ${result.strand ? html`<span className="tag">${result.strand}</span>` : null}
                      </div>
                    </article>
                  `,
                )}
              </div>
            `}
      </section>
    </section>
  `;
}

function SavePlan({ setStatus }) {
  const [form, setForm] = useState({ title: "", grade: "", subject: "", content: "" });

  function update(field, value) {
    setForm((current) => ({ ...current, [field]: value }));
  }

  async function save(event) {
    event.preventDefault();
    const payload = await api("/api/plans", {
      method: "POST",
      body: JSON.stringify(form),
    });
    setStatus(`Saved plan to ${payload.path}`);
    setForm({ title: "", grade: "", subject: "", content: "" });
  }

  return html`
    <form className="panel form" onSubmit=${save}>
      <h3>Save a Lesson Plan</h3>
      <div className="form-row">
        <label>
          Title
          <input value=${form.title} onChange=${(event) => update("title", event.target.value)} placeholder="Fractions Station Rotation" />
        </label>
        <label>
          Grade
          <input value=${form.grade} onChange=${(event) => update("grade", event.target.value)} placeholder="4" />
        </label>
        <label>
          Subject
          <input value=${form.subject} onChange=${(event) => update("subject", event.target.value)} placeholder="Math" />
        </label>
      </div>
      <label>
        Plan Markdown
        <textarea
          value=${form.content}
          onChange=${(event) => update("content", event.target.value)}
          placeholder=${"# Objectives\n- Students will..."}
        ></textarea>
      </label>
      <button className="primary" type="submit">Save Plan</button>
    </form>
  `;
}

function App() {
  const [view, setView] = useState("plan");
  const [status, setStatus] = useState("Dashboard ready.");
  const assist = usePiiAssist();

  const header = useMemo(() => {
    const active = views.find(([id]) => id === view);
    return active ? active[1] : "Dashboard";
  }, [view]);

  return html`
    <div className="app">
      <aside className="sidebar">
        <div className="brand">
          <h1>Dewey</h1>
          <p>Instructional planning workspace</p>
        </div>
        <nav className="nav" aria-label="Dashboard views">
          ${views.map(
            ([id, label]) => html`
              <button className=${view === id ? "active" : ""} key=${id} onClick=${() => setView(id)}>
                ${label}
              </button>
            `,
          )}
        </nav>
      </aside>
      <main className="main">
        <header className="topbar">
          <div>
            <h2>${header}</h2>
            <p>Local-first controls for plans, profile context, SOLs, and WIDA.</p>
          </div>
          <${PiiAssistToggle} assist=${assist} />
          <div className="status" role="status">${status}</div>
        </header>
        ${view === "plan" ? html`<${PlanLesson} setStatus=${setStatus} assist=${assist} />` : null}
        ${view === "library" ? html`<${LessonLibrary} setStatus=${setStatus} />` : null}
        ${view === "profile" ? html`<${Profile} setStatus=${setStatus} />` : null}
        ${view === "standards" ? html`<${Standards} setStatus=${setStatus} />` : null}
        ${view === "save" ? html`<${SavePlan} setStatus=${setStatus} />` : null}
      </main>
    </div>
  `;
}

createRoot(document.getElementById("root")).render(html`<${App} />`);
