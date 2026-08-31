import { api } from "./api.js";
import { escapeHtml, icon, openDrawer, openModal, setBusy, showToast } from "./ui.js";

const serviceGlyph = (name) => (name === "web" ? "W" : name.slice(0, 1).toUpperCase());

export function createServicesPanel({ root, onChanged }) {
  let rows = [];

  function render() {
    root.innerHTML = rows.length ? rows.map((service) => {
      const running = service.state === "running";
      const status = running ? "running" : service.error ? "error" : "stopped";
      const primaryAction = running ? "down" : "up";
      const primaryLabel = running ? "停止" : "启动";
      return `<tr>
        <td><div class="service-name"><span class="service-icon">${escapeHtml(serviceGlyph(service.name))}</span><span>${escapeHtml(service.name)}</span></div></td>
        <td><span class="status ${status}">${escapeHtml(service.state)}</span></td>
        <td class="mono">${service.pid || '<span class="muted">—</span>'}</td>
        <td class="mono">${service.port || '<span class="muted">—</span>'}</td>
        <td>${service.url ? `<div class="url-cell"><a href="${escapeHtml(service.url)}" target="_blank" rel="noreferrer">${escapeHtml(service.url)}</a><button class="copy-button" data-copy="${escapeHtml(service.url)}" title="复制 URL">${icon("copy")}</button></div>` : '<span class="muted">—</span>'}</td>
        <td><div class="actions">
          <button class="button small ${running ? "danger" : "primary"}" data-service-action="${primaryAction}" data-service="${escapeHtml(service.name)}">${icon(running ? "stop" : "play")}${primaryLabel}</button>
          <button class="button small" data-service-action="restart" data-service="${escapeHtml(service.name)}" title="重启">${icon("restart")}<span class="sr-only">重启</span></button>
          <button class="button small" data-port="${escapeHtml(service.name)}" title="端口设置">端口</button>
          <button class="button small" data-logs="${escapeHtml(service.name)}" title="查看日志">日志</button>
        </div></td>
      </tr>`;
    }).join("") : '<tr><td colspan="6" class="empty">暂无服务配置</td></tr>';
  }

  async function action(service, actionName, button, body = {}) {
    setBusy(button, true);
    try {
      await api.serviceAction(service, actionName, body);
      showToast(`${service} ${actionName === "down" ? "已停止" : actionName === "up" ? "已启动" : "已重启"}`);
      await refresh();
    } catch (error) {
      showToast("服务操作失败", error.message, "error");
    } finally {
      setBusy(button, false);
    }
  }

  function portModal(service) {
    const current = rows.find((item) => item.name === service);
    openModal({
      title: `设置 ${service} 端口`,
      submitText: "应用",
      body: `<div class="form-field"><label>端口策略</label><div class="radio-row"><label><input type="radio" name="port-mode" value="fixed" checked>指定端口</label><label><input type="radio" name="port-mode" value="auto">自动分配</label></div></div><div class="form-field" style="margin-top:14px"><label for="port-value">端口</label><input id="port-value" name="port" type="number" min="1" max="65535" value="${current?.port || ""}" placeholder="例如 8080"></div><p class="form-help">自动分配会优先使用该服务上次记录的端口和 preferred port。</p>`,
      onSubmit: async (form, close) => {
        const mode = form.get("port-mode");
        const port = Number(form.get("port"));
        const button = root.querySelector(`[data-port="${CSS.escape(service)}"]`);
        if (mode === "fixed" && (!Number.isInteger(port) || port < 1 || port > 65535)) throw new Error("请输入有效端口");
        await api.serviceAction(service, mode === "auto" ? "restart" : "set-port", mode === "auto" ? { auto_port: true } : { port });
        close();
        showToast(`${service} 端口已更新`);
        await refresh();
        if (button) button.blur();
      },
    });
  }

  async function showLogs(service) {
    const drawer = openDrawer({ title: `${service} 日志`, meta: "最近 80 行", content: `<pre class="log-viewer">正在读取日志…</pre>` });
    const viewer = drawer.root.querySelector(".log-viewer");
    try {
      const result = await api.logs(service, 80);
      viewer.textContent = result.content || "暂无日志";
      viewer.scrollTop = viewer.scrollHeight;
    } catch (error) {
      viewer.textContent = `读取失败：${error.message}`;
    }
  }

  root.addEventListener("click", async (event) => {
    const copy = event.target.closest("[data-copy]");
    if (copy) {
      try {
        await navigator.clipboard.writeText(copy.dataset.copy);
        showToast("URL 已复制");
      } catch { showToast("复制失败", "请手动复制链接", "error"); }
      return;
    }
    const port = event.target.closest("[data-port]");
    if (port) { portModal(port.dataset.port); return; }
    const logs = event.target.closest("[data-logs]");
    if (logs) { await showLogs(logs.dataset.logs); return; }
    const button = event.target.closest("[data-service-action]");
    if (button) await action(button.dataset.service, button.dataset.serviceAction, button);
  });

  async function refresh() {
    rows = await api.services();
    render();
    onChanged?.(rows);
    return rows;
  }

  return { refresh, getRows: () => rows };
}
