import { api } from "./api.js";
import { escapeHtml, icon, openModal, setBusy, showToast } from "./ui.js";

export function createTunnelsPanel({ root, addButton, ensureButton, onChanged }) {
  let rows = [];

  function render() {
    root.innerHTML = rows.length ? rows.map((tunnel) => {
      const running = tunnel.state === "running";
      return `<tr>
        <td><span class="mono">${escapeHtml(tunnel.name)}</span></td>
        <td><span class="mono">${escapeHtml(tunnel.host)}</span></td>
        <td><span class="mono">localhost:${tunnel.local_port} <span class="muted">→</span> ${tunnel.remote_host || "127.0.0.1"}:${tunnel.remote_port}</span></td>
        <td><span class="status ${running ? "running" : "stopped"}">${running ? "运行中" : "已停止"}</span><div class="muted mono">${tunnel.pid || "—"}</div></td>
        <td><div class="actions"><button class="button small subtle" data-ensure="${escapeHtml(tunnel.name)}">${icon("restart")}确保</button><button class="button small danger" data-remove="${escapeHtml(tunnel.name)}">${icon("trash")}删除</button></div></td>
      </tr>`;
    }).join("") : '<tr><td colspan="5" class="empty">暂无隧道规则</td></tr>';
  }

  function newTunnelModal() {
    openModal({
      title: "新建 SSH 隧道",
      submitText: "建立隧道",
      body: `<div class="form-grid"><div class="form-field full"><label>名称</label><input name="name" required pattern="[A-Za-z0-9_-]+" placeholder="例如 api-tunnel"></div><div class="form-field"><label>SSH Host</label><input name="host" required placeholder="ssh config 中的 Host"></div><div class="form-field"><label>远端 Host</label><input name="remote_host" value="127.0.0.1" required></div><div class="form-field"><label>本地端口</label><input name="local_port" type="number" min="1" max="65535" required placeholder="18080"></div><div class="form-field"><label>远端端口</label><input name="remote_port" type="number" min="1" max="65535" required placeholder="8080"></div></div>`,
      onSubmit: async (form, close) => {
        const data = Object.fromEntries(form.entries());
        data.local_port = Number(data.local_port);
        data.remote_port = Number(data.remote_port);
        await api.addTunnel(data);
        close();
        showToast("隧道已建立", data.name);
        await refresh();
      },
    });
  }

  async function ensure(name, button) {
    setBusy(button, true, "恢复中…");
    try { await api.ensureTunnels(name); showToast("隧道已确保", name || "全部隧道"); await refresh(); }
    catch (error) { showToast("隧道恢复失败", error.message, "error"); }
    finally { setBusy(button, false); }
  }

  root.addEventListener("click", async (event) => {
    const ensureButtonForRow = event.target.closest("[data-ensure]");
    if (ensureButtonForRow) { await ensure(ensureButtonForRow.dataset.ensure, ensureButtonForRow); return; }
    const remove = event.target.closest("[data-remove]");
    if (remove && window.confirm(`确定删除隧道「${remove.dataset.remove}」？`)) {
      setBusy(remove, true, "删除中…");
      try { await api.removeTunnel(remove.dataset.remove); showToast("隧道已删除", remove.dataset.remove); await refresh(); }
      catch (error) { showToast("删除失败", error.message, "error"); setBusy(remove, false); }
    }
  });
  addButton?.addEventListener("click", newTunnelModal);
  ensureButton?.addEventListener("click", () => ensure());

  async function refresh() {
    rows = await api.tunnels();
    render();
    onChanged?.(rows);
    return rows;
  }
  return { refresh, getRows: () => rows };
}
