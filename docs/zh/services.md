# 服务管理

一个 LocalSM 服务就是 `services.yaml` 里的一条命令模板。LocalSM 不理解你的服务在
做什么，它只负责端口、日志、进程和状态。

## 生命周期命令

```sh
LocalSM up [服务名]        # 省略服务名则启动全部
LocalSM down [服务名]
LocalSM restart [服务名]
LocalSM status [服务名]
LocalSM logs <服务名> [--lines N]
LocalSM set-port <服务名> <端口>
LocalSM exec <服务名> <命令>...
```

`up` 对已在运行的服务是幂等的——它直接返回当前状态，不会起第二个进程。

## 进程模型

`up` 用 `start_new_session` 把 `start` 命令拉起为脱离终端的新会话，stdout 与 stderr
都重定向到 `~/.local/state/localsm/logs/<服务名>.log`，pid 写进
`~/.local/state/localsm/pids/<服务名>.pid`。因为进程脱离了控制终端，关掉启动它的终端
窗口不会带走服务。

`down` 向整个进程组发 `SIGTERM`，最多等 5 秒，仍活着则发 `SIGKILL`，之后再执行服务
自己的 `stop` 命令（如果配了）。发信号给进程组而不是单个 pid，是为了带走 shell 包装
器拉起的子进程。

命令一律通过 `$SHELL`（缺省 `/bin/zsh`）执行，所以你能在 `start` 里直接用别名之外的
shell 语法、管道和环境展开。

服务也可以交给 launchd 托管，那时进程由系统拉起。见[launchd 服务模式](launchd.md)。

## 端口分配

三条规则按优先级：

1. 显式指定：`LocalSM up api --port 8080`
2. 粘性端口：上次成功使用的端口，记在 `~/.local/state/localsm/ports.json`
3. `preferred_port`，再退到 `port_range` 或顶层 `port_pool` 里第一个空闲端口

粘性端口是刻意的：重启服务通常应该回到同一个地址，否则你收藏的链接和写死的配置都会
失效。首选端口被占用时，LocalSM 默认报错而不是悄悄换一个；想让它自己挑：

```sh
LocalSM up api --auto-port      # 允许从池里换一个空闲端口
LocalSM set-port api 9000           # 改端口并按服务定义的方式生效
```

`up` 只负责「确保它在跑」，不搬家：对着一个已经在跑的服务 `up --port 9000`，LocalSM 会
报错并让你改用 `restart --port 9000`，而不是返回成功却什么都没做。

`set-port` 命令会执行服务的 `set_port` 命令序列（如果配了），否则等价于按新端口重启。这
让「改端口」对需要先写配置文件再 reload 的服务也能工作。`set_port` 模板里可以用
`{current_port}` 引用切换前的端口，方便先连上旧 manager 再让它换端口。

## 状态判定

`status` 报告的每个服务包含：

| 字段 | 含义 |
| --- | --- |
| `state` | `running` / `stopped` |
| `pid` | 进程 id，未运行或未知时为 `null` |
| `port` | 运行中是它实际在跑的端口，停止时是它下次会回到的端口 |
| `url` | 访问地址，只在运行中且 `url_from_log` 打开时有值 |
| `managed_by` | `detached` / `launchd` / `null` |

判定按顺序尝试四件事：

1. pid 文件里的进程是否活着（`ps` 检查状态位再 `kill -0`，僵尸进程算死）
2. 是否存在同名 launchd agent——有则 pid 与端口从 launchd 读
3. 服务是否配了 `status_cmd`——有则执行它并解析输出
4. 都没有，算 `stopped`

所以你手动 `kill` 掉一个服务，`status` 会立刻反映出来，不会因为 pid 文件还在就撒谎；
陈旧的 pid 文件会被顺手清掉。

端口和地址遵循同一条规则：**报告现在成立的事**。运行中的端口以日志为准（服务可能没绑到
给它的端口），日志没提就是 LocalSM 分配的那个；停止后端口变成「下次启动会落在哪」——
launchd 下是冻结端口，否则是粘性端口。`url` 则在停止时清空：面板会把它渲染成可点的
链接，而那后面已经没有东西在听了。

## 从日志解析 URL

很多开发服务器在启动时才知道自己的最终地址（挑了别的端口，或带了随机 token）。配
`url_from_log: true` 让 LocalSM 从日志里抓真实 URL，包括 fragment 部分（例如
`#token=...`），而不是用 `http://127.0.0.1:<端口>` 猜。

## 外部托管的服务

有些服务由别的东西托管（brew services、Docker、公司自己的 supervisor），LocalSM 起
不了也停不了，但你仍想在一处看到它。给它配 `status_cmd`：

```yaml
services:
  db:
    start: "brew services start postgresql"
    status_cmd: "brew services info postgresql"
```

LocalSM 执行 `status_cmd`，输出里出现 `running` / `运行中` / `已运行` 就算在跑，出现
`stopped` / `not running` / `未运行` 就算没跑。命令还会顺带从输出里抓 `pid N` 和
`port N`（或 `端口 N`）。

全部字段定义见[配置参考](configuration.md)。
