# 故障排查

## 先跑 doctor

```sh
LocalSM doctor --local-only     # 只查本机，秒级返回
LocalSM doctor                  # 加上远端 SSH 连通性，慢一些
```

`doctor` 分组报告本地工具（`uv`、`ssh`、`osascript`、Ghostty）、Python 依赖、每个服务
`start` 命令的可执行文件、配置文件有效性、state 目录可写性。任何 `FAIL` 都会让退出码
变成 1，所以可以直接挂进脚本。

远端那一节只检查你在 `tunnels.yaml` 里用到的 Host，不是 `~/.ssh/config` 里的全部主机：
一台和 LocalSM 无关的机器宕了不该算 LocalSM 有问题，诊断命令也不该去连你没让它连的
主机。没有配置隧道时这一节直接跳过。

`WARN` 不影响退出码：缺 Ghostty 只是没法用 `LocalSM ssh --app ghostty`，某个服务的命令
不在 PATH 上也许是因为它需要先激活环境。

## 配置相关

### 命令说找不到配置

```text
LocalSM: no configuration at /Users/you/.config/localsm/services.yaml. Run 'LocalSM init' to create one.
```

读类命令遇到这个只是在 stderr 提醒你，退出码仍是 0。跑 `LocalSM init` 生成模板。

### 明明有配置，LocalSM 却看不到

先确认它在看哪里：

```sh
LocalSM config
```

它会打印当前生效的配置目录与 state 目录。看不到你期望的路径，通常是环境里残留了
`LOCALSM_CONFIG_DIR` / `LOCALSM_STATE_DIR` / `LOCALSM_ROOT`：

```sh
env | grep LOCALSM
```

这在开发时尤其容易发生——为了在仓库内跑设了 `LOCALSM_ROOT="$PWD"`，然后忘了它还在
当前 shell 里。

### 升级后配置像丢了

0.2.0 之前 LocalSM 从安装目录推导配置路径，配置放在仓库的 `config/` 下。现在统一在
`~/.config/localsm/`。0.x 不提供兼容垫片，手动搬一次：

```sh
mkdir -p ~/.config/localsm
cp path/to/repo/config/*.yaml ~/.config/localsm/
```

## 服务起不来

### `failed to start` 后面跟着一行日志

LocalSM 起进程后短暂等待再检查存活，进程立刻退出就报这个，并附上日志最后一行。完整日
志：

```sh
LocalSM logs api --lines 100
```

最常见的原因是 `start` 命令依赖的环境不在。LocalSM 用 `$SHELL` 执行命令但**不是**登录
shell，所以只在 `.zshrc` 里定义的函数和别名不可用（launchd 模式反而是登录 shell）。把
需要的东西写成完整命令，或者用 `working_dir` 加相对路径。

### 端口被占用

```sh
LocalSM up api --auto-port      # 允许换一个空闲端口
LocalSM set-port api 9001           # 指定新端口
```

想知道谁占着：

```sh
lsof -nP -iTCP:8080 -sTCP:LISTEN
```

### 状态显示 running，实际连不上

`status` 报告的是进程存活，不是服务可用。进程在但没绑上端口的情况确实存在（配置错误、
启动到一半卡住）。看日志，以及给服务配 `status_cmd` 让 LocalSM 用你自己的判据。

如果服务的真实端口和 LocalSM 报的不一致，多半是服务自己换了端口。打开
`url_from_log: true` 让 LocalSM 从日志里读真实地址。

### `down` 之后进程还在

`down` 向进程组发 `SIGTERM`，等 5 秒后 `SIGKILL`。仍然残留通常意味着子进程脱离了原进
程组（比如 `start` 里自己又 `setsid` 了一次，或者服务是个把工作交给守护进程的客户端）。
给它配 `stop` 命令，用服务自己的方式关：

```yaml
services:
  api:
    start: "myservice up --port {port}"
    stop: "myservice down"
```

## launchd 相关

### `down` 被拒绝

服务在 launchd 托管下，`KeepAlive` 会立刻把它拉回来。要真的停掉：

```sh
LocalSM disable api
```

### enable 之后服务反复重启

看退出码与日志：

```sh
LocalSM --json status api | jq '.pid, .managed_by'
LocalSM logs api --lines 100
launchctl print gui/$(id -u)/com.localsm.api
```

起来就崩的服务在 `KeepAlive` 下会以 10 秒（`ThrottleInterval`）为间隔反复重启。修好启
动问题，或者先 `disable` 掉再排查。

### launchd 模式下命令找不到

反过来的坑：launchd 用登录 shell（`-lc`）执行命令，而 detached 模式不是。所以有的服务
在 launchd 下能跑、detached 下不能，或者相反。两种模式下都测一遍。

### 改不了端口

端口冻结在 plist 里。用 `LocalSM set-port api 9000`（会重写并重载 plist），或者
`disable` 后用新端口 `enable`。带 `--port` 的 `up` / `restart` 会被拒绝。

## 隧道相关

### 隧道 running 但连不上

`state` 只反映 ssh 进程是否存在。看 ssh 自己说了什么：

```sh
tail -50 ~/.local/state/localsm/logs/tunnel-api.log
```

也很可能是远端服务没在跑——隧道健康，另一头是空的。用 `LocalSM remote scan` 确认远端
端口真的在监听。

### 隧道时不时就死

正常，网络会断。`ServerAliveCountMax=3` 保证 ssh 会干净退出而不是半死不活，把它拉回来
是 `ensure` 的事：

```sh
LocalSM tunnel ensure
```

想让它自动，把 `ensure` 挂进 launchd 定时任务，或者依赖面板——面板不会自动 ensure，但
`stopped` 状态一眼可见。

### add 报本地端口已占用

`add` 动手前先检查，所以不会留下半成品。换个本地端口，或者先停掉占用者。

## 远端扫描相关

### 主机 unreachable

先确认 SSH 本身通不通：

```sh
ssh my-pod true
```

扫描用 `BatchMode=yes`，所以任何需要交互输入密码或密钥口令的连接都会失败。把认证配成
免交互（密钥加 agent），扫描才能工作。

### 主机可达但没发现端口

`reachable: true` 加空 `ports` 加 `error`，说明连上了但探测命令失败。看 `error`：远端
四种探测方式（`ss`、`lsof`、`netstat`、`python3` 读 `/proc/net/tcp`）都没有的话就是这
个症状。

`reachable: true` 加空 `ports` 加 `error: null`，就是真的什么都没监听。

### 扫描很慢

默认每台 8 秒超时，最多 12 台并发。主机多且有不通的，最坏情况是 `主机数/12 × 超时`。
调短超时或只扫你关心的：

```sh
LocalSM remote scan pod-a pod-b --timeout 3
```

## 面板相关

### 403 refused Host

面板只回应 loopback 名字。你大概是通过一个自定义 hosts 别名访问的：

```sh
LOCALSM_WEB_ALLOWED_HOSTS=dev.local LocalSM web
```

原因见 [Web 面板](web.md)的安全模型。

### 改了配置面板不显示

面板监听 `services.yaml` 的 mtime，前端 5 秒刷一次，所以最多等 5 秒。超过就检查面板进
程和你的 CLI 是不是在看同一个配置目录（面板由 `LocalSM web` 起，可能带着不同的
`LOCALSM_*` 环境变量）。

### 面板起不来

它就是个普通服务：

```sh
LocalSM logs web --lines 50
LocalSM web --foreground        # 直接在终端看报错
```

端口 8765 被占用是最常见的原因。

## 还是不行

带上这些信息开 issue：

```sh
LocalSM --version
LocalSM config
LocalSM doctor --local-only
```

`LocalSM config` 与 `doctor` 的输出不含服务的 `start` 命令内容，但会包含服务名与路径，
贴之前扫一眼。
