import { api } from "./api.js";
import { escapeHtml, showToast } from "./ui.js";

export function createConfigPanel({ root, meta }) {
  let snapshot = null;

  function render() {
    if (!snapshot) {
      root.innerHTML = '<tr><td colspan="4" class="empty">正在读取配置…</td></tr>';
      return;
    }
    root.innerHTML = snapshot.services.length
      ? snapshot.services
          .map(
            (service) => `<tr>
        <td><span>${escapeHtml(service.name)}</span></td>
        <td class="mono">${service.preferred_port || '<span class="muted">auto</span>'}</td>
        <td class="mono config-start">${escapeHtml(service.start)}</td>
        <td class="mono">${service.working_dir ? escapeHtml(service.working_dir) : '<span class="muted">—</span>'}</td>
      </tr>`,
          )
          .join("")
      : '<tr><td colspan="4" class="empty">暂无服务定义，运行 LocalSM init 生成模板</td></tr>';
    meta.textContent = `${snapshot.services_file} · 端口池 ${snapshot.port_pool[0]}-${snapshot.port_pool[1]} · 只读，用 ${snapshot.edit_command} 修改`;
  }

  async function refresh() {
    try {
      snapshot = await api.config();
    } catch (error) {
      showToast("配置读取失败", error.message, "error");
      throw error;
    }
    render();
    return snapshot;
  }

  render();
  return { refresh, getSnapshot: () => snapshot };
}
