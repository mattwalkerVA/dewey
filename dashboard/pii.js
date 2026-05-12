/**
 * Browser-local PII assist using transformers.js.
 *
 * Runs an NER model entirely in the browser (WebGPU when available, WASM
 * fallback). Model weights are downloaded once from the Hugging Face CDN
 * and cached by transformers.js in IndexedDB. No text leaves the browser
 * during inference.
 */

const MODEL_ID = "Xenova/bert-base-NER";
const MODEL_LIB = "https://cdn.jsdelivr.net/npm/@xenova/transformers@2.17.2";

let modulePromise = null;
let pipelinePromise = null;
let backendLabel = "Not loaded";
let progressListeners = new Set();

function notifyProgress(event) {
  for (const listener of progressListeners) {
    try {
      listener(event);
    } catch (error) {
      console.error("PII progress listener failed:", error);
    }
  }
}

export function onProgress(listener) {
  progressListeners.add(listener);
  return () => progressListeners.delete(listener);
}

export function getBackendLabel() {
  return backendLabel;
}

export function isLoaded() {
  return Boolean(pipelinePromise);
}

async function loadModule() {
  if (!modulePromise) {
    modulePromise = import(/* @vite-ignore */ MODEL_LIB);
  }
  return modulePromise;
}

async function detectBackend(transformers) {
  try {
    if (typeof navigator !== "undefined" && "gpu" in navigator && navigator.gpu) {
      const adapter = await navigator.gpu.requestAdapter();
      if (adapter) return "webgpu";
    }
  } catch (error) {
    console.warn("WebGPU probe failed; falling back to WASM.", error);
  }
  return "wasm";
}

/**
 * Lazy-load the NER pipeline. Resolves to a callable pipeline.
 */
export async function loadPiiAssist() {
  if (pipelinePromise) return pipelinePromise;

  pipelinePromise = (async () => {
    notifyProgress({ status: "loading-library" });
    const transformers = await loadModule();
    const backend = await detectBackend(transformers);
    backendLabel = backend === "webgpu" ? "Loaded · WebGPU" : "Loaded · WASM";

    notifyProgress({ status: "loading-model", backend });
    const pipeline = await transformers.pipeline("token-classification", MODEL_ID, {
      quantized: true,
      device: backend === "webgpu" ? "webgpu" : undefined,
      progress_callback: (event) => notifyProgress(event),
    });

    notifyProgress({ status: "ready", backend });
    return pipeline;
  })().catch((error) => {
    pipelinePromise = null;
    backendLabel = "Failed to load";
    notifyProgress({ status: "error", message: String(error) });
    throw error;
  });

  return pipelinePromise;
}

/**
 * Run NER over `text` and return PERSON spans.
 * Returns an array of {start, end, text, score} sorted by start offset.
 */
export async function detectPersons(text) {
  if (!text || !text.trim()) return [];
  const pipeline = await loadPiiAssist();
  const raw = await pipeline(text, { ignore_labels: [] });
  return mergePersonSpans(text, raw);
}

/**
 * Merge BIO/IO sub-tokens into whole-name spans.
 * transformers.js's `aggregation_strategy` isn't always reliable across
 * versions, so we do the merge ourselves.
 */
function mergePersonSpans(text, tokens) {
  const spans = [];
  let current = null;

  const isPerson = (entity) => entity && /PER/i.test(entity);
  const isBegin = (entity) => entity && /^B-/i.test(entity);

  for (const token of tokens) {
    const entity = token.entity || token.entity_group || "";
    if (!isPerson(entity)) {
      if (current) spans.push(current);
      current = null;
      continue;
    }

    const start = token.start ?? null;
    const end = token.end ?? null;
    if (start == null || end == null) continue;

    if (!current || isBegin(entity) || start > current.end + 1) {
      if (current) spans.push(current);
      current = { start, end, score: token.score ?? 0, count: 1 };
    } else {
      current.end = Math.max(current.end, end);
      current.score = ((current.score * current.count) + (token.score ?? 0)) / (current.count + 1);
      current.count += 1;
    }
  }
  if (current) spans.push(current);

  return spans
    .map((span) => ({
      start: span.start,
      end: span.end,
      text: text.slice(span.start, span.end),
      score: span.score,
    }))
    .filter((span) => span.text.trim().length > 1);
}

/**
 * Apply a set of accepted span keys to a text, replacing accepted spans
 * with `[REDACTED]`. `acceptedKeys` is a Set of `${start}:${end}` strings.
 * Spans whose text no longer matches at start:end (e.g. user typed since
 * detection) are dropped silently.
 */
export function applyRedactions(text, spans, acceptedKeys) {
  if (!spans?.length) return text;
  const accepted = spans
    .filter((span) => acceptedKeys.has(`${span.start}:${span.end}`))
    .filter((span) => text.slice(span.start, span.end) === span.text)
    .sort((a, b) => b.start - a.start);
  let out = text;
  for (const span of accepted) {
    out = out.slice(0, span.start) + "[REDACTED]" + out.slice(span.end);
  }
  return out;
}
