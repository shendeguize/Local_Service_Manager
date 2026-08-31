const DEFAULT_TIMEOUT = 15000;

async function request(path, options = {}) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), options.timeout ?? DEFAULT_TIMEOUT);
  const headers = { Accept: "application/json", ...(options.body ? { "Content-Type": "application/json" } : {}) };
  try {
    const response = await fetch(path, { ...options, headers: { ...headers, ...(options.headers || {}) }, signal: controller.signal });
    const text = await response.text();
    let payload = {};
    try { payload = text ? JSON.parse(text) : {}; } catch { payload = { content: text }; }
    if (!response.ok) throw new Error(payload.error || payload.content || `请求失败（${response.status}）`);
    return payload;
  } catch (error) {
    if (error.name === "AbortError") throw new Error("请求超时，请稍后重试");
    throw error;
  } finally {
    clearTimeout(timer);
  }
}

const json = (method, body) => ({ method, ...(body === undefined ? {} : { body: JSON.stringify(body) }) });

export const api = {
  services: () => request("/api/services"),
  serviceAction: (name, action, body = {}) => request(`/api/services/${encodeURIComponent(name)}/${action}`, json("POST", body)),
  logs: (name, lines = 80) => request(`/api/logs/${encodeURIComponent(name)}?lines=${encodeURIComponent(lines)}`),
  remote: () => request("/api/remote"),
  scanRemote: (hosts = [], timeout = 8) => request("/api/remote/scan", { ...json("POST", { hosts, timeout }), timeout: (timeout + 5) * 1000 }),
  tunnels: () => request("/api/tunnels"),
  addTunnel: (body) => request("/api/tunnels", json("POST", body)),
  ensureTunnels: (name) => request("/api/tunnels/ensure", json("POST", name ? { name } : {})),
  removeTunnel: (name) => request(`/api/tunnels/${encodeURIComponent(name)}`, { method: "DELETE" }),
  ssh: (host, app) => request(`/api/ssh/${encodeURIComponent(host)}`, json("POST", { app })),
};
