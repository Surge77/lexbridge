// Every value from the server is written with textContent, never innerHTML: answers are
// model output and must not be able to inject markup.
"use strict";

const $ = (id) => document.getElementById(id);
let traceId = null;

function show(el, visible) { el.hidden = !visible; }

function chip(sectionId) {
  const li = document.createElement("li");
  const b = document.createElement("button");
  b.type = "button";
  b.textContent = sectionId.replace(":", " ");
  b.addEventListener("click", () => openSection(sectionId));
  li.append(b);
  return li;
}

function fill(list, ids) {
  list.replaceChildren(...ids.map(chip));
}

async function call(path, options) {
  let response;
  try {
    response = await fetch(path, options);
  } catch {
    throw new Error("Could not reach LexBridge. Check your connection and try again.");
  }
  if (response.status === 204) return null;
  // A proxy in front of the app can answer with an HTML error page, not our JSON.
  const body = await response.json().catch(() => null);
  if (!response.ok || body === null) {
    const wait = response.headers.get("Retry-After");
    const message = body?.error?.message ?? `The service is unavailable (HTTP ${response.status}).`;
    throw new Error(wait ? `${message} (try again in ${wait}s)` : message);
  }
  return body;
}

function fail(error) {
  $("error").textContent = error.message;
  show($("error"), true);
}

function render(answer) {
  $("status").textContent = answer.status;
  $("status").dataset.status = answer.status;
  $("act").textContent = answer.act ?? "";
  show($("act"), Boolean(answer.act));
  show($("cached"), answer.cached);
  $("text").textContent = answer.text;
  fill($("cites"), answer.citations);
  show($("cites-wrap"), answer.citations.length > 0);
  fill($("sources"), answer.sources);
  show($("sources-wrap"), answer.sources.length > 0);
  traceId = answer.trace_id;
  show($("feedback"), Boolean(traceId));
  show($("thanks"), false);
  voting(true);
  show($("result"), true);
}

async function ask(event) {
  event.preventDefault();
  const question = $("question").value.trim();
  if (!question) return;
  const body = { question };
  if ($("date").value) body.offence_date = $("date").value;
  $("submit").disabled = true;
  $("submit").textContent = "Checking…";
  show($("error"), false);
  try {
    render(await call("/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }));
  } catch (e) {
    fail(e);
  } finally {
    $("submit").disabled = false;
    $("submit").textContent = "Ask";
  }
}

async function openSection(sectionId) {
  show($("error"), false);
  try {
    const [section, map] = await Promise.all([
      call(`/section/${encodeURIComponent(sectionId)}`),
      call(`/map/${encodeURIComponent(sectionId)}`),
    ]);
    $("section-title").textContent = `${section.act} ${section.number}: ${section.title}`;
    const other = map.replaced_by.length ? `Replaced by ${map.replaced_by.join(", ")}`
      : map.replaces.length ? `Replaces ${map.replaces.join(", ")}` : "";
    $("section-map").textContent = other.replaceAll(":", " ");
    $("section-text").textContent = section.text;
    show($("section"), true);
    $("section").scrollIntoView({ behavior: "smooth", block: "nearest" });
  } catch (e) {
    fail(e);
  }
}

function voting(enabled) {
  $("feedback").querySelectorAll("button").forEach((b) => { b.disabled = !enabled; });
}

async function feedback(event) {
  const helpful = event.target.dataset.helpful;
  if (helpful === undefined || !traceId) return;
  show($("error"), false);
  voting(false);  // one vote per answer
  try {
    await call("/feedback", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ trace_id: traceId, helpful: helpful === "true" }),
    });
    show($("thanks"), true);
  } catch (e) {
    voting(true);
    fail(e);
  }
}

document.addEventListener("DOMContentLoaded", () => {
  $("ask").addEventListener("submit", ask);
  $("feedback").addEventListener("click", feedback);
  $("close").addEventListener("click", () => show($("section"), false));
  document.querySelectorAll(".examples button").forEach((b) =>
    b.addEventListener("click", () => { $("question").value = b.dataset.q; $("question").focus(); }));
});
