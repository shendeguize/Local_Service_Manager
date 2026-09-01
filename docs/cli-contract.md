# CLI 输出契约

LocalSM 的每条命令都有两种输出模式：默认的人类可读文本，和 `--json` 的机器可读
JSON。脚本请一律使用 `--json`，人类文本的措辞不在兼容性承诺内。

## 全局开关

| 开关 | 作用 |
| --- | --- |
| `--json` | 输出 JSON 文档到 stdout，替代人类文本 |
| `--quiet` | 抑制信息性 stdout；错误仍写 stderr |

两个开关放在子命令前后都可以，`LocalSM --json status` 与 `LocalSM status --json`
等价。同时给出时 `--json` 优先：JSON 是被显式请求的载荷，不会被 `--quiet` 抑制。

## 退出码

| 码 | 含义 |
| --- | --- |
| `0` | 成功 |
| `1` | LocalSM 运行错误（服务、隧道、终端、配置），错误信息写 stderr |
| `2` | 用法错误（argparse 校验失败），或未处理的命令分支 |
| 其他 | 仅 `exec`：透传子进程退出码 |

`doctor` 在任一检查为 `FAIL` 时返回 `1`，否则 `0`。

配置文件不存在时，读类命令仍返回 `0`，并在 stderr 打印一行指向 `LocalSM init`
的提示——「尚未配置」不是故障。`doctor` 是唯一例外，它把缺失配置报为 `FAIL`。

## 各命令的 JSON 形态

### 服务对象

`up`、`restart`、`down`、`status` 始终返回**数组**，即使只指定了一个服务：

```json
[
  {
    "name": "web",
    "state": "running",
    "pid": 42123,
    "port": 8765,
    "url": "http://127.0.0.1:8765/",
    "log": "...",
    "error": null
  }
]
```

`state` 取值为 `running` 或 `stopped`。`set-port` 与 `web` 返回单个服务对象（非数组）。

### 其他命令

| 命令 | JSON 形态 |
| --- | --- |
| `init` | `{"config_dir": str, "created": [str], "skipped": [str]}` |
| `config` | `{"config_dir", "services_file", "tunnels_file", "state_dir", "port_pool": [int, int], "tunnels": int, "services": [{"name", "preferred_port", "start"}]}` |
| `doctor` | `{"checks": [{"section", "name", "status", "detail"}], "failed": int}` |
| `exec` | `{"service", "command": [str], "exit_code": int}` |
| `logs` | `{"service", "lines": int, "content": str}` |
| `remote scan` | `[{"host", "reachable": bool, "ports": [int], "error", "tunnels": {port: [name]}}]` |
| `tunnel add` | 单个隧道对象，含 `pid` 与 `state` |
| `tunnel rm` | `{"removed": name}` |
| `tunnel list` / `tunnel ensure` | 隧道对象数组 |
| `ssh` | `{"launched": host, "app": "ghostty"\|"terminal"}` |

隧道对象的字段为 `name`、`host`、`local_port`、`remote_host`、`remote_port`，
`list` 与 `ensure` 另附 `state` 和 `pid`。

`doctor` 的 `status` 取值为 `PASS`、`WARN`、`FAIL`；只有 `FAIL` 影响退出码。

## 示例

```sh
# 取出所有正在运行的服务名
LocalSM --json status | jq -r '.[] | select(.state == "running") | .name'

# 在 CI 里静默检查环境
LocalSM --quiet doctor --local-only || echo "环境不健康"

# 找出没有隧道覆盖的远端监听端口
LocalSM --json remote scan | jq -r '.[] | .tunnels | to_entries[] | select(.value == []) | .key'
```
