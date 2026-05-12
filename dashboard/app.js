import React, { useEffect, useMemo, useState } from "https://esm.sh/react@18.3.1";
import { createRoot } from "https://esm.sh/react-dom@18.3.1/client";
import htm from "https://esm.sh/htm@3.1.1";

const html = htm.bind(React.createElement);

const views = [
  ["library", "Lesson Library"],
  ["profile", "Teacher Profile"],
  ["standards", "Standards"],
  ["save", "Save Plan"],
];

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.error || "Request failed.");
  }
  return payload;
}

function Empty({ children }) {
  return html`<div className="empty">${children}</div>`;
}

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
  const [view, setView] = useState("library");
  const [status, setStatus] = useState("Dashboard ready.");

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
          <div className="status" role="status">${status}</div>
        </header>
        ${view === "library" ? html`<${LessonLibrary} setStatus=${setStatus} />` : null}
        ${view === "profile" ? html`<${Profile} setStatus=${setStatus} />` : null}
        ${view === "standards" ? html`<${Standards} setStatus=${setStatus} />` : null}
        ${view === "save" ? html`<${SavePlan} setStatus=${setStatus} />` : null}
      </main>
    </div>
  `;
}

createRoot(document.getElementById("root")).render(html`<${App} />`);
