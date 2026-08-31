import { api } from "./api.js";
import { escapeHtml, icon, openModal, setBusy, showToast } from "./ui.js";

export function createRemotePanel({ root, scanButton, scanMeta, onChanged }) {
  let snapshot = { scanned_at: null, results: [] };

  function render() {
    const results = snapshot.results || [];
    root.innerHTML = results.length ? results.map((host) => {
      const ports = host.ports || [];
      const tunnelMap = host.tunnels || {};
      const covered = Object.values(tunnelMap).flat();
      const portMarkup = ports.length
        ? ports.map((port) => `<button class="port-chip ${tunnelMap[String(port)]?.length ? "covered" : ""}" data-remote-port="${port}" data-remote-host="${escapeHtml(host.host)}" title="为 ${escapeHtml(host.host)}:${port} 创建隧道">${port}</button>`).join("")
        : '<span class="muted">未发现监听端口</span>';
      const error = host.error ? `<div class="muted" title="${escapeHtml(host.error)}">${escapeHtml(host.error)}</div>` : "";
      return `<tr>
        <td><div class="host-name">${icon("server")}<span>${escapeHtml(host.host)}</span></div>${error}</td>
        <td><span class="status ${host.reachable ? "reachable" : "unreachable"}">${host.reachable ? "可达" : "不可达"}</span></td>
        <td><div class="port-chips">${portMarkup}</div></td>
        <td><div class="tunnel-tags">${covered.length ? covered.map((tag) => `<span class="tunnel-tag">${escapeHtml(tag)}</span>`).join("") : '<span class="muted">—</span>'}</div></td>
        <td><div class="actions"><button class="button small" data-ssh-host="${escapeHtml(host.host)}">${icon("terminal")}SSH</button></div></td>
      </tr>`;
    }).join("") : '<tr><td colspan="5" class="empty">点击右上角扫描 SSH config 中的主机</td></tr>';
    if (scanMeta) scanMeta.textContent = snapshot.scanned_at ? `上次扫描 ${formatTime(snapshot.scanned_at)}` : "尚未扫描";
  }

  function formatTime(value) {
    try { return new Intl.DateTimeFormat("zh-CN", { hour: "2-digit", minute: "2-digit", second: "2-digit" }).format(new Date(value)); }
    catch { return "时间未知"; }
  }

  function tunnelModal(host, remotePort) {
    openModal({
      title: "新建 SSH 隧道",
      submitText: "建立隧道",
      body: `<div class="form-grid"><div class="form-field full"><label>名称</label><input name="name" required pattern="[A-Za-z0-9_-]+" placeholder="例如 pod-api" autofocus></div><div class="form-field"><label>SSH Host</label><input name="host" value="${escapeHtml(host)}" required></div><div class="form-field"><label>远端 Host</label><input name="remote_host" value="127.0.0.1" required></div><div class="form-field"><label>本地端口</label><input name="local_port" type="number" min="1" max="65535" required placeholder="例如 18080"></div><div class="form-field"><label>远端端口</label><input name="remote_port" type="number" min="1" max="65535" value="${remotePort}" required></div></div><p class="form-help">LocalSM 不会改写 ~/.ssh/config，隧道规则只保存在自己的配置中。</p>`,
      onSubmit: async (form, close) => {
        const data = Object.fromEntries(form.entries());
        data.local_port = Number(data.local_port);
        data.remote_port = Number(data.remote_port);
        await api.addTunnel(data);
        close();
        showToast("隧道已建立", `${data.name}: localhost:${data.local_port} → ${data.host}:${data.remote_port}`);
        onChanged?.();
      },
    });
  }

  function sshModal(host) {
    openModal({
      title: `连接 ${host}`,
      submitText: "打开终端",
      body: `<div class="form-field"><label>终端应用</label><select name="app"><option value="ghostty">Ghostty</option><option value="terminal">Terminal.app</option></select></div><p class="form-help">会在新终端窗口中执行 ssh ${escapeHtml(host)}。</p>`,
      onSubmit: async (form, close) => {
        await api.ssh(host, form.get("app"));
        close();
        showToast("终端已打开", host);
      },
    });
  }

  async function scan() {
    setBusy(scanButton, true, "扫描中…");
    if (scanMeta) scanMeta.innerHTML = '<span class="spinner"></span> 正在并行连接主机';
    try {
      snapshot = { scanned_at: new Date().toISOString(), results: await api.scanRemote() };
      render();
      showToast("远端扫描完成", `${snapshot.results.length} 个 Host`);
      onChanged?.(snapshot);
    } catch (error) {
      showToast("远端扫描失败", error.message, "error");
      if (scanMeta) scanMeta.textContent = "扫描失败";
    } finally {
      setBusy(scanButton, false);
    }
  }

  root.addEventListener("click", (event) => {
    const port = event.target.closest("[data-remote-port]");
    if (port) { tunnelModal(port.dataset.remoteHost, Number(port.dataset.remotePort)); return; }
    const ssh = event.target.closest("[data-ssh-host]");
    if (ssh) sshModal(ssh.dataset.sshHost);
  });
  scanButton?.addEventListener("click", scan);

  async function refresh() {
    snapshot = await api.remote();
    render();
    onChanged?.(snapshot);
    return snapshot;
  }
  return { refresh, scan, getSnapshot: () => snapshot };
}
