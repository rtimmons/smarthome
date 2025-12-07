const statusEl = document.querySelector("[data-status]");
const rowsEl = document.getElementById("url-rows");
const emptyEl = document.getElementById("empty-state");
const tableWrapperEl = document.getElementById("table-wrapper");
const listSubtitleEl = document.getElementById("list-subtitle");
const formEl = document.getElementById("create-form");
const urlInputEl = document.getElementById("url-input");
const refreshBtn = document.getElementById("refresh-btn");
const clientConfig = window.__TINYURL_CONFIG__ || {};

const api = {
  async list() {
    return request("api/urls");
  },
  async create(url) {
    return request("api/urls", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url }),
    });
  },
  async reset(slug) {
    return request(`api/urls/${slug}/reset`, { method: "POST" });
  },
  async remove(slug) {
    return request(`api/urls/${slug}`, { method: "DELETE" });
  },
};

function setStatus(message, tone = "muted") {
  statusEl.textContent = message;
  statusEl.className = `status ${tone}`;
}

async function request(path, options = {}) {
  const res = await fetch(path, options);
  if (res.status === 204) return null;
  const data = await res.json().catch(() => null);
  if (!res.ok) {
    const msg = data?.error || `Request failed (${res.status})`;
    throw new Error(msg);
  }
  return data;
}

function formatTime(iso) {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString();
}

function buildShortUrl(slug) {
  const baseUrl = resolveBaseUrl();
  return `${baseUrl.replace(/\/+$/, "")}/${slug}`;
}

function resolveBaseUrl() {
  if (clientConfig.baseUrl) {
    return clientConfig.baseUrl.replace(/\/+$/, "");
  }
  const port = clientConfig.port || 4100;
  const { protocol, hostname } = window.location;
  return `${protocol}//${hostname}:${port}`;
}

function renderList(items) {
  rowsEl.innerHTML = "";
  if (!items.length) {
    emptyEl.classList.remove("hidden");
    tableWrapperEl.classList.add("hidden");
    listSubtitleEl.textContent = "Nothing here yet.";
    return;
  }

  emptyEl.classList.add("hidden");
  tableWrapperEl.classList.remove("hidden");
  listSubtitleEl.textContent = `${items.length} link${items.length === 1 ? "" : "s"}`;

  for (const item of items) {
    const shortUrl = buildShortUrl(item.slug);
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>
        <div class="slug-link">
          <span class="slug-pill">${item.slug}</span>
          <button class="btn ghost copy-btn" data-slug="${item.slug}" title="Copy short URL">Copy</button>
        </div>
      </td>
      <td>
        <a href="${item.target}" target="_blank" rel="noopener">${item.target}</a>
      </td>
      <td>
        <div>${item.visitCount}</div>
        <div class="visits">${item.lastVisitedAt ? `Last: ${formatTime(item.lastVisitedAt)}` : "Never"}</div>
      </td>
      <td class="visits">
        ${item.visits.length ? item.visits.map((v) => formatTime(v)).join("<br/>") : "No visits yet"}
      </td>
      <td>
        <div class="actions">
          <a class="btn ghost" href="${shortUrl}" target="_blank" rel="noopener">Open</a>
          <button class="btn ghost reset-btn" data-slug="${item.slug}">Reset</button>
          <button class="btn danger delete-btn" data-slug="${item.slug}">Delete</button>
        </div>
      </td>
    `;
    rowsEl.appendChild(tr);
  }
}

async function refresh() {
  try {
    setStatus("Refreshing…");
    const list = await api.list();
    renderList(list);
    setStatus("Up to date");
  } catch (err) {
    console.error(err);
    setStatus(err.message, "danger");
  }
}

formEl.addEventListener("submit", async (event) => {
  event.preventDefault();
  const url = urlInputEl.value.trim();
  if (!url) return;
  try {
    setStatus("Creating…");
    await api.create(url);
    urlInputEl.value = "";
    await refresh();
    setStatus("Created");
  } catch (err) {
    console.error(err);
    setStatus(err.message, "danger");
  }
});

refreshBtn.addEventListener("click", refresh);

rowsEl.addEventListener("click", async (event) => {
  const target = event.target;
  if (!(target instanceof HTMLElement)) return;
  const slug = target.dataset.slug;
  if (!slug) return;

  if (target.classList.contains("reset-btn")) {
    event.preventDefault();
    try {
      setStatus(`Resetting ${slug}…`);
      await api.reset(slug);
      await refresh();
      setStatus(`Reset ${slug}`);
    } catch (err) {
      console.error(err);
      setStatus(err.message, "danger");
    }
  }

  if (target.classList.contains("delete-btn")) {
    event.preventDefault();
    const confirmed = confirm(`Delete /${slug}?`);
    if (!confirmed) return;
    try {
      setStatus(`Deleting ${slug}…`);
      await api.remove(slug);
      await refresh();
      setStatus(`Deleted ${slug}`);
    } catch (err) {
      console.error(err);
      setStatus(err.message, "danger");
    }
  }

  if (target.classList.contains("copy-btn")) {
    event.preventDefault();
    try {
      const shortUrl = buildShortUrl(slug);
      if (navigator.clipboard && navigator.clipboard.writeText) {
        await navigator.clipboard.writeText(shortUrl);
        setStatus(`Copied ${shortUrl}`);
      } else if (legacyCopy(shortUrl)) {
        setStatus(`Copied ${shortUrl}`);
      } else {
        setStatus(`Copy not supported in this browser`, "danger");
      }
    } catch (err) {
      console.error(err);
      setStatus("Copy failed", "danger");
    }
  }
});

refresh();

function legacyCopy(text) {
  const el = document.createElement("textarea");
  el.value = text;
  el.setAttribute("readonly", "");
  el.style.position = "absolute";
  el.style.left = "-9999px";
  document.body.appendChild(el);
  el.select();
  let copied = false;
  try {
    copied = document.execCommand("copy");
  } catch (err) {
    copied = false;
  } finally {
    document.body.removeChild(el);
  }
  if (!copied) {
    // Last resort prompt so users can manually copy.
    const response = window.prompt("Copy the short URL", text);
    copied = Boolean(response);
  }
  return copied;
}
