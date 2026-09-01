import { createConfigPanel } from "./config.js";
import { createRemotePanel } from "./remote.js";
import { createServicesPanel } from "./services.js";
import { createTunnelsPanel } from "./tunnels.js";
import { icon, showToast } from "./ui.js";

const state = { services: [], remote: { scanned_at: null, results: [] }, tunnels: [] };

function updateMetrics() {
  const running = state.services.filter((service) => service.state === "running").length;
  const reachable = (state.remote.results || []).filter((host) => host.reachable).length;
  const tunnelRunning = state.tunnels.filter((tunnel) => tunnel.state === "running").length;
  document.querySelector("#metric-running").textContent = `${running}`;
  document.querySelector("#metric-total").textContent = `${state.services.length}`;
  document.querySelector("#metric-reachable").textContent = state.remote.scanned_at ? `${reachable}` : "—";
  document.querySelector("#metric-tunnels").textContent = `${tunnelRunning}`;
  document.querySelector("#metric-running-detail").textContent = running ? "进程正在提供服务" : "当前没有运行中的服务";
  document.querySelector("#metric-reachable-detail").textContent = state.remote.scanned_at ? `${state.remote.results.length} 个 Host 已扫描` : "点击扫描远端";
  document.querySelector("#metric-tunnels-detail").textContent = state.tunnels.length ? `${tunnelRunning} 条隧道运行中` : "暂无配置规则";
}

async function loadServices(panel) {
  try { state.services = await panel.refresh(); } catch (error) { showToast("服务状态读取失败", error.message, "error"); }
  updateMetrics();
}

async function loadRemote(panel) {
  try { state.remote = await panel.refresh(); } catch (error) { showToast("远端缓存读取失败", error.message, "error"); }
  updateMetrics();
}

async function loadTunnels(panel) {
  try { state.tunnels = await panel.refresh(); } catch (error) { showToast("隧道状态读取失败", error.message, "error"); }
  updateMetrics();
}

async function loadConfig(panel) {
  try { await panel.refresh(); } catch { /* the panel already reported it */ }
}

function applyTheme(theme) {
  document.documentElement.dataset.theme = theme;
  localStorage.setItem("localsm-theme", theme);
  const button = document.querySelector("#theme-toggle");
  button.innerHTML = icon(theme === "dark" ? "sun" : "moon");
  button.title = theme === "dark" ? "切换到浅色模式" : "切换到深色模式";
}

function setupTheme() {
  const saved = localStorage.getItem("localsm-theme");
  const initial = saved || (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
  applyTheme(initial);
  document.querySelector("#theme-toggle").addEventListener("click", () => {
    applyTheme(document.documentElement.dataset.theme === "dark" ? "light" : "dark");
  });
}

async function refreshAll(panels, { notify = false } = {}) {
  const results = await Promise.allSettled([
    loadServices(panels.services),
    loadRemote(panels.remote),
    loadTunnels(panels.tunnels),
    loadConfig(panels.config),
  ]);
  if (notify && results.every((result) => result.status === "fulfilled")) showToast("数据已刷新", "服务、远端和隧道状态已同步");
}

function setup() {
  document.querySelector("#refresh-all").innerHTML = `${icon("refresh")}刷新`;
  document.querySelector("#scan-remote").innerHTML = `${icon("globe")}扫描远端`;
  document.querySelector("#ensure-tunnels").innerHTML = `${icon("restart")}确保全部`;
  document.querySelector("#add-tunnel").innerHTML = `${icon("plus")}新建隧道`;
  setupTheme();

  const panels = {
    services: createServicesPanel({
      root: document.querySelector("#services-body"),
      onChanged: (rows) => { state.services = rows; updateMetrics(); },
    }),
    remote: createRemotePanel({
      root: document.querySelector("#remote-body"),
      scanButton: document.querySelector("#scan-remote"),
      scanMeta: document.querySelector("#scan-meta"),
      onChanged: (snapshot) => { if (snapshot) state.remote = snapshot; updateMetrics(); },
    }),
    tunnels: createTunnelsPanel({
      root: document.querySelector("#tunnels-body"),
      addButton: document.querySelector("#add-tunnel"),
      ensureButton: document.querySelector("#ensure-tunnels"),
      onChanged: (rows) => { if (rows) state.tunnels = rows; updateMetrics(); },
    }),
    config: createConfigPanel({
      root: document.querySelector("#config-body"),
      meta: document.querySelector("#config-meta"),
    }),
  };
  document.querySelector("#refresh-all").addEventListener("click", () => refreshAll(panels, { notify: true }));
  document.querySelector("#auto-refresh").addEventListener("change", (event) => {
    if (event.target.checked) showToast("自动刷新已开启", "服务和隧道每 5 秒同步一次");
  });
  let timer = setInterval(() => {
    if (document.querySelector("#auto-refresh").checked) refreshAll(panels);
  }, 5000);
  window.addEventListener("beforeunload", () => clearInterval(timer), { once: true });
  refreshAll(panels);
}

setup();
