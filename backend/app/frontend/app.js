/**
 * Qviqa Feed — a static, client-only SPA in the Firebase Hosting style: no
 * server-side rendering, every request goes straight from the browser to a
 * REST/NDJSON API (the same shape a Firestore- or Functions-backed Firebase
 * app would use). `appConfig` plays the role of firebaseConfig — swap
 * apiBase to point this same static bundle at any backend deployment, and
 * the whole app/ directory can be pushed to Firebase Hosting unchanged
 * (`firebase init hosting` with app/frontend as the public dir, then
 * `firebase deploy`).
 */
const appConfig = {
  apiBase: window.location.origin,
};

const feedEl = document.getElementById("feed");
const statusEl = document.getElementById("status");
const sourcesEl = document.getElementById("sources");
const keywordsInput = document.getElementById("keywords");
const connectBtn = document.getElementById("connect");

async function loadSources() {
  const res = await fetch(`${appConfig.apiBase}/api/sources`);
  const data = await res.json();
  sourcesEl.innerHTML = data.sources
    .map((s) => `<span class="source-pill">${escapeHtml(s.title)}</span>`)
    .join("");
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

function renderItem(item) {
  const li = document.createElement("li");
  li.className = "card";
  const tags = (item.matched_keywords || [])
    .filter((k) => k !== "*")
    .map((k) => `<span class="tag">#${escapeHtml(k)}</span>`)
    .join(" ");
  li.innerHTML = `
    <div class="card-head">
      <strong>${escapeHtml(item.title)}</strong>
      <span class="source">${escapeHtml(item.source)}</span>
    </div>
    ${item.price ? `<div class="price">${escapeHtml(item.price)}</div>` : ""}
    <p>${escapeHtml((item.text || "").slice(0, 240))}</p>
    <div class="card-foot">
      <a href="${item.url}" target="_blank" rel="noopener">открыть →</a>
      ${tags}
    </div>`;
  feedEl.prepend(li);
}

async function streamFeed() {
  feedEl.innerHTML = "";
  statusEl.textContent = "поток открыт…";
  connectBtn.disabled = true;

  const keywords = keywordsInput.value.trim();
  const url = `${appConfig.apiBase}/api/stream${keywords ? `?keywords=${encodeURIComponent(keywords)}` : ""}`;
  let count = 0;

  try {
    const res = await fetch(url);
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop();
      for (const line of lines) {
        if (!line.trim()) continue;
        renderItem(JSON.parse(line));
        count += 1;
        statusEl.textContent = `получено: ${count}`;
      }
    }
    statusEl.textContent = `готово · ${count} заказ(ов)`;
  } catch (err) {
    statusEl.textContent = `ошибка: ${err.message}`;
  } finally {
    connectBtn.disabled = false;
  }
}

connectBtn.addEventListener("click", streamFeed);
loadSources();
