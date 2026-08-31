# 配置参考

LocalSM 默认从项目目录读取配置：

```text
config/services.yaml   服务定义与端口池
config/tunnels.yaml    SSH 隧道规则
state/                 pidfile、日志、端口状态、扫描缓存
```

## 路径环境变量

| 变量 | 作用 |
| --- | --- |
| `LOCALSM_ROOT` | 覆盖项目根目录 |
| `LOCALSM_CONFIG_DIR` | 覆盖配置目录 |
| `LOCALSM_STATE_DIR` | 覆盖运行状态目录 |
| `PYTHON` | 命令模板 `{python}` 使用的 Python 可执行文件 |

例如，为测试使用一套隔离状态：

```sh
LOCALSM_STATE_DIR=/tmp/localsm-state ./LocalSM status
```

## services.yaml

顶层 `port_pool` 是自动分配的闭区间：

```yaml
port_pool: [8000, 8999]
services:
  demo:
    start: "python -m http.server {port}"
    preferred_port: 8080
    port_range: [8100, 8199]
    set_port: ["demo config {port}", "demo restart"]
    stop: "demo stop"
    status_cmd: "demo status"
    url_from_log: true
    working_dir: "~/workspace"
    env:
      MODE: development
```

字段说明：

- `start`：启动命令模板，必须存在。LocalSM 使用 shell 执行它。
- `preferred_port`：服务首选端口；被占用时只有传入 `--auto-port` 才会继续寻找。
- `port_range`：该服务自己的自动分配范围；缺省使用顶层 `port_pool`。
- `set_port`：端口修改命令，可为字符串或命令列表。每条命令都能使用
  `{port}`。
- `stop`：停止命令，可为字符串或命令列表。
- `status_cmd`：外部托管服务的状态命令。返回包含 `running`、`运行中` 或
  `已运行` 时，LocalSM 会把它识别为运行中。
- `url_from_log`：从日志中解析实际 URL，保留 URL fragment（例如 Kimi
  的 `#token=...`）。
- `working_dir`：启动、停止、exec 命令使用的工作目录。
- `env`：附加环境变量。

命令模板可用变量：

- `{port}`：LocalSM 分配或用户请求的端口。
- `{current_port}`：执行 `set_port` 时服务当前的端口，适合需要先连接旧
  manager 再切换配置的服务。
- `{python}`：当前运行 LocalSM 的 Python 路径。

`dshc` 这种服务可以用多命令端口模板：

```yaml
dshc:
  start: "dshc up --port {port}"
  set_port:
    - "dshc config set manager.port {port} --port {current_port}"
    - "dshc restart --port {current_port}"
```

## tunnels.yaml

```yaml
tunnels:
  - name: api-pod
    host: my-pod
    local_port: 18080
    remote_host: 127.0.0.1
    remote_port: 8080
```

`host` 必须是 `~/.ssh/config` 中的 Host alias。LocalSM 通过 detached
`ssh -N -L` 进程建立隧道，并把 pid 写入 `state/pids/tunnel-*.pid`。
`tunnel ensure` 会检测进程，不存在时按原规则重建。

## state 布局

```text
state/
├── logs/<service>.log
├── logs/tunnel-<name>.log
├── pids/<service>.pid
├── pids/tunnel-<name>.pid
├── ports.json
└── remote_scan.json
```

state 是运行时数据，已被 `.gitignore` 排除。删除 `ports.json` 会清除粘性
端口记录，但不会停止现有进程。
