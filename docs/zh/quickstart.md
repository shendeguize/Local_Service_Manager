# 快速上手

假设你已经按[安装](install.md)装好了 LocalSM。

## 1. 生成初始配置

```sh
LocalSM init
```

这会在 `~/.config/localsm/` 写入带注释的 `services.yaml` 和 `tunnels.yaml`。
`init` 永远不覆盖已存在的文件，重复运行是安全的。

## 2. 定义你的服务

```sh
LocalSM edit
```

`edit` 用 `$EDITOR` 打开 `services.yaml`，退出后告诉你哪些服务被增删改动，以及
哪些正在运行的服务需要重启才能生效。

一个最小定义只需要 `start`：

```yaml
port_pool: [8000, 8999]

services:
  api:
    start: "uvicorn app:api --port {port}"
    preferred_port: 8080
    url_from_log: true
```

`{port}` 会被 LocalSM 分配的端口替换。`url_from_log: true` 让 LocalSM 从日志里
解析真实访问地址，而不是靠猜。全部字段见[配置参考](configuration.md)。

## 3. 启动与查看

```sh
LocalSM up api        # 启动单个服务
LocalSM up            # 启动全部服务
LocalSM status        # 查看状态、pid、端口、URL
LocalSM logs api      # 查看日志尾部
LocalSM down api      # 停止
```

端口被占用时，加 `--auto-port` 让 LocalSM 从端口池里挑一个空闲端口：

```sh
LocalSM up api --auto-port
```

LocalSM 会记住每个服务上次成功使用的端口，所以下次重启通常会回到同一个端口。

## 4. 打开 Web 面板

```sh
LocalSM web
```

面板默认在 `http://127.0.0.1:8765/`。它提供服务启停、改端口、日志抽屉、远端扫描、
SSH 终端和隧道管理。想在当前终端里前台运行、按 Ctrl-C 停止：

```sh
LocalSM web --foreground
```

## 5. 让服务开机自启

```sh
LocalSM enable api
```

这会生成一个 launchd agent，登录时自动拉起，进程意外退出时自动重启。交回 LocalSM
管理：

```sh
LocalSM disable api
```

细节和端口冻结的原因见[launchd 服务模式](launchd.md)。

## 写脚本

所有命令都支持 `--json`。人类可读文本的措辞不在兼容性承诺内，脚本请一律用
`--json`：

```sh
# 列出正在运行的服务
LocalSM --json status | jq -r '.[] | select(.state == "running") | .name'

# 在 CI 里静默检查环境
LocalSM --quiet doctor --local-only || echo "环境不健康"
```

完整约定见[输出契约](cli-contract.md)。

## 接下来

- 远端主机的监听端口：[远端扫描](remote.md)
- 把远端端口映射到本机：[SSH 隧道](tunnels.md)
- 出问题了：[故障排查](troubleshooting.md)
