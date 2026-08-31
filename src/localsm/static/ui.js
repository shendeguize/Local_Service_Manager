const iconPaths = {
  refresh: '<path d="M20 11a8 8 0 0 0-14.9-4L3 9"/><path d="M3 4v5h5"/><path d="M4 13a8 8 0 0 0 14.9 4L21 15"/><path d="M21 20v-5h-5"/>',
  sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2m0 16v2M4.93 4.93l1.41 1.41m11.32 11.32 1.41 1.41M2 12h2m16 0h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41"/>',
  moon: '<path d="M20.5 14.5A8.5 8.5 0 0 1 9.5 3.5 8.5 8.5 0 1 0 20.5 14.5Z"/>',
  play: '<path d="m8 5 11 7-11 7V5Z"/>',
  stop: '<rect x="6" y="6" width="12" height="12" rx="1"/>',
  restart: '<path d="M20 11a8 8 0 1 0 1 4"/><path d="M20 4v7h-7"/>',
  terminal: '<path d="m4 5 6 6-6 6"/><path d="M12 17h8"/>',
  copy: '<rect x="8" y="8" width="10" height="10" rx="1"/><path d="M16 8V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h2"/>',
  chevron: '<path d="m6 9 6 6 6-6"/>',
  close: '<path d="m6 6 12 12M18 6 6 18"/>',
  server: '<rect x="4" y="4" width="16" height="6" rx="1"/><rect x="4" y="14" width="16" height="6" rx="1"/><path d="M8 7h.01M8 17h.01"/>',
  globe: '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c2.2 2.4 3.3 5.4 3.3 9s-1.1 6.6-3.3 9c-2.2-2.4-3.3-5.4-3.3-9S9.8 5.4 12 3Z"/>',
  link: '<path d="M10 13a5 5 0 0 0 7.1.1l1.4-1.4a5 5 0 0 0-7.1-7.1L10.6 5.4"/><path d="M14 11a5 5 0 0 0-7.1-.1l-1.4 1.4a5 5 0 0 0 7.1 7.1l.8-.8"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  trash: '<path d="M4 7h16M10 11v6m4-6v6M6 7l1 13h10l1-13M9 7V4h6v3"/>',
  check: '<path d="m5 12 4 4L19 6"/>',
  alert: '<path d="M10.3 4.3 2.8 17a2 2 0 0 0 1.7 3h15a2 2 0 0 0 1.7-3L13.7 4.3a2 2 0 0 0-3.4 0Z"/><path d="M12 9v4m0 4h.01"/>',
};

export const icon = (name, className = "") => `<svg class="${className}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${iconPaths[name] || iconPaths.server}</svg>`;

export const escapeHtml = (value) => String(value ?? "").replace(/[&<>"']/g, (character) => ({
  "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;",
}[character]));

export function showToast(title, detail = "", type = "success") {
  const stack = document.querySelector("#toast-stack");
  const toast = document.createElement("div");
  toast.className = `toast ${type}`;
  toast.innerHTML = `<span class="toast-icon">${icon(type === "error" ? "alert" : "check")}</span><div class="toast-copy"><div class="toast-title">${escapeHtml(title)}</div><div class="toast-detail">${escapeHtml(detail)}</div></div>`;
  stack.append(toast);
  setTimeout(() => toast.remove(), 4200);
}

export function setBusy(button, busy, label = "处理中…") {
  if (!button) return;
  if (busy) {
    button.dataset.label = button.innerHTML;
    button.disabled = true;
    button.classList.add("loading");
    button.innerHTML = `<span class="spinner"></span>${label}`;
  } else {
    button.disabled = false;
    button.classList.remove("loading");
    button.innerHTML = button.dataset.label || button.innerHTML;
  }
}

export function openModal({ title, body, submitText = "确认", onSubmit }) {
  const root = document.querySelector("#modal-root");
  root.hidden = false;
  root.innerHTML = `<div class="modal" role="dialog" aria-modal="true" aria-labelledby="modal-title"><div class="modal-header"><h3 id="modal-title">${escapeHtml(title)}</h3><button class="close-button" type="button" data-close>${icon("close")}</button></div><form id="modal-form"><div class="modal-body">${body}</div><div class="modal-footer"><button class="button" type="button" data-close>取消</button><button class="button primary" type="submit">${escapeHtml(submitText)}</button></div></form></div>`;
  const close = () => { root.hidden = true; root.innerHTML = ""; };
  root.querySelectorAll("[data-close]").forEach((button) => button.addEventListener("click", close));
  root.addEventListener("click", (event) => { if (event.target === root) close(); }, { once: true });
  root.querySelector("#modal-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const submit = event.currentTarget.querySelector('[type="submit"]');
    setBusy(submit, true);
    try { await onSubmit(new FormData(event.currentTarget), close); } catch (error) { showToast("操作失败", error.message, "error"); setBusy(submit, false); }
  });
  root.querySelector("input, select")?.focus();
  return close;
}

export function openDrawer({ title, meta = "", content = "" }) {
  const root = document.querySelector("#drawer-root");
  root.hidden = false;
  root.innerHTML = `<aside class="drawer-panel" role="dialog" aria-modal="true"><div class="drawer-header"><div><h3>${escapeHtml(title)}</h3><div class="drawer-meta">${escapeHtml(meta)}</div></div><button class="close-button" data-close>${icon("close")}</button></div><div class="drawer-content">${content}</div><div class="drawer-footer"><button class="button" data-close>关闭</button></div></aside>`;
  const close = () => { root.hidden = true; root.innerHTML = ""; };
  root.querySelectorAll("[data-close]").forEach((button) => button.addEventListener("click", close));
  root.addEventListener("click", (event) => { if (event.target === root) close(); }, { once: true });
  return { root, close };
}
