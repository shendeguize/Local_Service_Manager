# launchd 服务模式

默认情况下 LocalSM 起的服务是脱离终端的普通进程：关终端不影响它，但重启机器就没了，
崩溃也不会自己起来。想要开机自启和崩溃自愈，把服务交给 macOS 的 launchd。

launchd 托管是**按服务 opt-in** 的，不是全局开关。detached 仍然是默认模式。

## 交出与收回

```sh
LocalSM enable api                # 交给 launchd
LocalSM enable api --port 8080     # 指定要冻结的端口
LocalSM disable api               # 收回 LocalSM 管理
LocalSM status api                # managed_by 字段显示当前归属
```

`enable` 依次做四件事：

1. 如果该服务正被 LocalSM 以 detached 方式运行，先停掉它——launchd 绑不上一个还被别
   人占着的端口
2. 确定端口并**冻结**进 plist（沿用粘性端口分配，或用 `--port` 指定）
3. 写 `~/Library/LaunchAgents/com.localsm.<服务名>.plist`
4. `launchctl bootout` 清掉上一代，再 `launchctl bootstrap gui/<uid>` 装载新的；
   `RunAtLoad` 让它立刻跑起来

先 bootout 再 bootstrap 是必要的：launchd 不会替换一个已装载的 label，重复 `enable`
若不先卸载，新 plist 根本不生效。

`disable` 反向执行：`launchctl bootout`，删除 plist，服务回到 LocalSM 直管。它对没
被托管的服务也是安全的，只会告诉你本来就没托管。

## 为什么端口必须冻结

launchd 拉起服务的时候没有任何 LocalSM 进程在场——没人能去探测端口占用、更新
`ports.json`、把 `{port}` 填进命令模板。所以端口必须在 `enable` 那一刻定下来，渲染进
plist 的命令行里，同时以 `LOCALSM_PORT` 环境变量的形式写进 plist 供服务自己读取。

`status` 也从 plist 里读回这个冻结端口，所以即使服务当前没在跑，你依然能看到它将会
用哪个端口。

## 托管期间各命令的行为

| 命令 | 行为 |
| --- | --- |
| `up` | 委托给 `launchctl kickstart` |
| `down` | 拒绝，提示用 `disable`（launchd 会立刻把它拉回来） |
| `restart` | 委托给 `launchctl kickstart -k` |
| `status` | 从 `launchctl list` 读 pid 与上次退出码 |
| `set-port` | 用新端口重写并重载 plist |
| `up --port` / `restart --port` / `--auto-port` | 拒绝，端口已冻结 |

`down` 拒绝而不是「尽力而为」，是因为 plist 里配了 `KeepAlive`：你杀掉进程，launchd
几秒内就会把它拉回来，装作成功只会让人困惑。想真的停掉，用 `disable`。

带端口的 `up` / `restart` 被拒绝，是因为这类命令的语义是「这次用这个端口跑」，而
launchd 模式下端口是 plist 的属性而非本次启动的属性。要换端口就用 `LocalSM set-port`，
或者 `disable` 后重新 `enable`。

## 生成的 plist 长什么样

关键键值：

- `Label`：`com.localsm.<服务名>`
- `ProgramArguments`：`[$SHELL, "-lc", "<冻结端口后的 start 命令>"]`。走登录 shell 是
  为了让服务拿到和你手动启动时一样的 PATH 与环境
- `RunAtLoad`、`KeepAlive`：登录即启动、退出即重启
- `ThrottleInterval`：10 秒，显式写出而不依赖平台默认值，让 plist 自解释
- `StandardOutPath` / `StandardErrorPath`：都指向
  `~/.local/state/localsm/logs/<服务名>.log`，与 detached 模式同一个文件
- `WorkingDirectory`：服务的 `working_dir`（如果配了）
- `EnvironmentVariables`：服务的 `env` 加上 `LOCALSM_PORT`

日志路径归一是有意的：切换托管方式不该让你去别处找日志，`LocalSM logs` 在两种模式下
行为一致。

## 排查 launchd 托管的服务

`status --json` 里 `last_exit_status` 非零说明服务起来就崩了。日志在老地方：

```sh
LocalSM logs api --lines 100
```

想直接看系统视角：

```sh
launchctl print gui/$(id -u)/com.localsm.api
```

plist 是普通的 XML 文件，可以直接读来确认冻结的端口和命令。但不要手改——下次
`enable` 会整份重写，改动会丢。

## 什么时候不该用 launchd

launchd 适合「我希望它一直在」的服务：本地数据库、代理、长期后台任务。不适合一天要改
十次代码的开发服务器——那种情况下 `LocalSM restart` 走 detached 模式更快，也不会因为
`KeepAlive` 在你调试崩溃时反复重启。
