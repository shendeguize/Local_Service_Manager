/**
 * The demo's stand-in for the dashboard's HTTP layer.
 *
 * This file replaces static/api.js and nothing else: every other module the
 * dashboard ships runs unmodified, so what a visitor drives is the real front
 * end. State lives in memory, which is why a refresh resets everything.
 *
 * The starting state is fixtures.json, captured from the real Flask app by
 * scripts/gen_demo_fixtures.py. Transitions below reimplement the parts of the
 * Python backend a visitor can observe, including the refusals: `down` on a
 * launchd-managed service fails here exactly as it does on a real machine,
 * because pretending otherwise would teach the wrong thing.
 */

const fixtures = await fetch(new URL("./fixtures.json", import.meta.url)).then((response) => {
  if (!response.ok) throw new Error(`无法加载演示数据（${response.status}）`);
  return response.json();
});

const clone = (value) => JSON.parse(JSON.stringify(value));

/**
 * Latency, so the interface's pending states are visible rather than instant.
 * The test suite turns it off; nothing it asserts depends on the wait.
 */
const scale = globalThis.LOCALSM_DEMO_INSTANT ? 0 : 1;
const settle = (ms = 260) => new Promise((resolve) => setTimeout(resolve, ms * scale));

const state = {
  config: clone(fixtures.config),
  services: clone(fixtures.services),
  logs: clone(fixtures.logs),
  tunnels: clone(fixtures.tunnels),
  remote: clone(fixtures.remote),
  // The demo opens on a machine that was scanned a while ago, so the table has
  // something in it and pressing scan still visibly does something.
  scannedAt: new Date(Date.now() - 42 * 60 * 1000).toISOString(),
  // Sticky ports: the port each service last used successfully, which is what
  // makes a restart land back on the same address.
  lastPort: Object.fromEntries(
    fixtures.services.filter((service) => service.port).map((service) => [service.name, service.port]),
  ),
  nextPid: 43000,
};

const definition = (name) => state.config.services.find((item) => item.name === name);
const service = (name) => {
  const found = state.services.find((item) => item.name === name);
  if (!found) throw new Error(`unknown service ${name}`);
  return found;
};

const takenPorts = () =>
  new Set([
    ...state.services.filter((item) => item.state === "running").map((item) => item.port),
    ...state.tunnels.filter((item) => item.state === "running").map((item) => item.local_port),
  ]);

// Every caller stops the service first, so its own port is already free here,
// the same way the real allocator sees a released port.
function allocatePort(name, { requested, autoPort }) {
  const taken = takenPorts();
  if (requested) {
    if (taken.has(requested)) throw new Error(`端口 ${requested} 已被占用`);
    return requested;
  }
  const preferred = state.lastPort[name] ?? definition(name)?.preferred_port;
  if (preferred && !taken.has(preferred)) return preferred;
  if (!autoPort) {
    throw new Error(`端口 ${preferred} 已被占用，可勾选自动分配或指定其他端口`);
  }
  const [low, high] = state.config.port_pool;
  for (let port = low; port <= high; port += 1) {
    if (!taken.has(port)) return port;
  }
  throw new Error(`端口池 ${low}-${high} 已无空闲端口`);
}

/** The log line the captured service printed, with its port substituted. */
function startupLog(name, port) {
  const captured = state.logs[name]?.content ?? fixtures.logs[name]?.content;
  if (captured) return captured.replace(/127\.0\.0\.1:\d+/g, `127.0.0.1:${port}`);
  return `${name} listening on http://127.0.0.1:${port}/`;
}

function start(name, { requested, autoPort } = {}) {
  const target = service(name);
  if (target.state === "running") return target;
  const port = allocatePort(name, { requested, autoPort });
  const log = startupLog(name, port);
  Object.assign(target, {
    state: "running",
    pid: (state.nextPid += 137),
    port,
    url: definition(name)?.url_from_log ? `http://127.0.0.1:${port}/` : null,
    log,
    error: null,
    managed_by: target.managed_by === "launchd" ? "launchd" : "detached",
  });
  state.lastPort[name] = port;
  state.logs[name] = { service: name, lines: 40, content: log };
  return target;
}

function stop(name) {
  const target = service(name);
  if (target.managed_by === "launchd") {
    throw new Error(
      `${name} is managed by launchd, which would restart it immediately; run 'LocalSM disable ${name}' to stop it`,
    );
  }
  Object.assign(target, { state: "stopped", pid: null, url: null, error: null, managed_by: null });
  return target;
}

const actions = {
  up: (name, body) => start(name, { requested: body.port, autoPort: Boolean(body.auto_port) }),
  down: (name) => stop(name),
  restart: (name, body) => {
    const target = service(name);
    if (target.managed_by === "launchd") {
      // launchctl kickstart -k, which keeps the port frozen in the agent.
      target.pid = (state.nextPid += 137);
      return target;
    }
    const port = body.port ?? (body.auto_port ? undefined : target.port);
    Object.assign(target, { state: "stopped", pid: null, managed_by: null });
    return start(name, { requested: port, autoPort: Boolean(body.auto_port) });
  },
  "set-port": (name, body) => {
    const port = Number(body.port);
    if (!Number.isInteger(port) || port < 1 || port > 65535) throw new Error("port must be between 1 and 65535");
    const target = service(name);
    if (target.managed_by === "launchd") {
      // Rewrites and reloads the agent with the new frozen port.
      state.lastPort[name] = port;
      Object.assign(target, { port, url: `http://127.0.0.1:${port}/`, pid: (state.nextPid += 137) });
      state.logs[name] = { service: name, lines: 40, content: startupLog(name, port) };
      return target;
    }
    if (target.state === "stopped") {
      state.lastPort[name] = port;
      target.port = port;
      return target;
    }
    Object.assign(target, { state: "stopped", pid: null });
    return start(name, { requested: port });
  },
};

export const api = {
  async config() {
    await settle(120);
    return clone(state.config);
  },

  async services() {
    await settle(140);
    return clone(state.services);
  },

  async serviceAction(name, action, body = {}) {
    await settle();
    const handler = actions[action];
    if (!handler) throw new Error(`unknown action ${action}`);
    return clone(handler(name, body));
  },

  async logs(name, lines = 80) {
    await settle(180);
    const entry = state.logs[name];
    return { service: name, lines, content: entry?.content ?? "" };
  },

  async remote() {
    await settle(140);
    return { scanned_at: state.scannedAt, results: clone(state.remote) };
  },

  async scanRemote(hosts = []) {
    // Long enough that the scanning state is legible, since a real scan opens an
    // SSH connection per host.
    await settle(1400);
    const wanted = hosts.length ? new Set(hosts) : null;
    state.remote = state.remote.map((host) => {
      if (wanted && !wanted.has(host.host)) return host;
      return {
        ...host,
        tunnels: Object.fromEntries(
          host.ports.map((port) => [
            String(port),
            state.tunnels
              .filter((tunnel) => tunnel.host === host.host && tunnel.remote_port === port)
              .map((tunnel) => tunnel.name),
          ]),
        ),
      };
    });
    state.scannedAt = new Date().toISOString();
    return clone(state.remote);
  },

  async tunnels() {
    await settle(140);
    return clone(state.tunnels);
  },

  async addTunnel(body) {
    await settle(420);
    const name = String(body.name || "").trim();
    const host = String(body.host || "").trim();
    const localPort = Number(body.local_port);
    const remotePort = Number(body.remote_port);
    if (!name || !host) throw new Error("隧道名称与 SSH Host 不能为空");
    if (![localPort, remotePort].every((port) => Number.isInteger(port) && port >= 1 && port <= 65535)) {
      throw new Error("local and remote ports must be between 1 and 65535");
    }
    if (state.tunnels.some((tunnel) => tunnel.name === name)) throw new Error(`tunnel '${name}' already exists`);
    if (takenPorts().has(localPort)) throw new Error(`local port ${localPort} is already in use`);
    if (!state.remote.some((item) => item.host === host)) {
      throw new Error(`${host} 不在 ~/.ssh/config 中；演示可用的 Host：${state.remote.map((i) => i.host).join(", ")}`);
    }
    const tunnel = {
      name,
      host,
      local_port: localPort,
      remote_host: String(body.remote_host || "127.0.0.1"),
      remote_port: remotePort,
      state: "running",
      pid: (state.nextPid += 137),
    };
    state.tunnels.push(tunnel);
    return clone(tunnel);
  },

  async ensureTunnels(name) {
    await settle(520);
    const selected = name ? state.tunnels.filter((tunnel) => tunnel.name === name) : state.tunnels;
    if (name && !selected.length) throw new Error(`tunnel '${name}' not found`);
    for (const tunnel of selected) {
      if (tunnel.state !== "running") {
        tunnel.state = "running";
        tunnel.pid = state.nextPid += 137;
      }
    }
    return clone(selected);
  },

  async removeTunnel(name) {
    await settle(300);
    const index = state.tunnels.findIndex((tunnel) => tunnel.name === name);
    if (index === -1) throw new Error(`tunnel '${name}' not found`);
    state.tunnels.splice(index, 1);
    return { removed: name };
  },

  async ssh(host) {
    await settle(200);
    // The one action with no simulation: it opens a terminal application on the
    // machine running LocalSM, which a web page cannot and should not do.
    throw new Error(`演示环境无法打开终端。在本机上这会运行 ssh ${host}`);
  },
};
