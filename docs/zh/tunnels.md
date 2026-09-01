# SSH 隧道

LocalSM 的隧道是显式规则：你声明「本机某端口转发到某远端主机的某端口」，LocalSM 负
责把 `ssh -N -L` 进程拉起来、盯着它、需要时重建。它不做自动发现，也不猜你想转发什么。

## 命令

```sh
LocalSM tunnel add <名字> <主机> <本地端口> <远端端口> [--remote-host 主机]
LocalSM tunnel list
LocalSM tunnel ensure [名字]
LocalSM tunnel rm <名字>
```

`<主机>` 必须是 `~/.ssh/config` 里的 Host alias。LocalSM 不接受裸 IP 加一堆连接参数
——认证方式、跳板机、端口这些都该由你的 SSH 配置负责，LocalSM 只引用别名。

## 建立隧道

```sh
LocalSM tunnel add api my-pod 18080 8080
```

这条规则把本机 `127.0.0.1:18080` 转到 `my-pod` 上的 `127.0.0.1:8080`。远端目标默认是
`127.0.0.1`；如果要转发到远端主机能看见的另一台机器，用 `--remote-host`：

```sh
LocalSM tunnel add db my-pod 15432 5432 --remote-host db.internal
```

`add` 在动手之前会先检查本地端口是否空闲、名字是否重复，两者任一不满足就直接报错，不
会留下半成品。规则写入 `~/.config/localsm/tunnels.yaml`，pid 写入
`~/.local/state/localsm/pids/tunnel-<名字>.pid`，ssh 自己的输出进
`~/.local/state/localsm/logs/tunnel-<名字>.log`。

## ssh 进程的参数

LocalSM 起的每条隧道都带这几个选项，原因值得说明：

| 选项 | 为什么 |
| --- | --- |
| `-N` | 不执行远端命令，只做转发 |
| `ExitOnForwardFailure=yes` | 端口没绑上就让 ssh 直接退出，而不是留一个假装在工作的连接 |
| `ServerAliveInterval=30` | 每 30 秒探活，让半死的连接尽快暴露 |
| `ServerAliveCountMax=3` | 连续三次探活失败就断开，交给 `ensure` 重建 |

`ExitOnForwardFailure` 是关键的一条：没有它，端口冲突会得到一个连着但不转发的 ssh，
症状表现为「隧道明明在跑，连过去却拒绝连接」。有了它，失败就是失败。

## 自愈

隧道断了不会自己回来——`ServerAliveCountMax` 只保证 ssh 会干净地退出。把它拉回来是
`ensure` 的事：

```sh
LocalSM tunnel ensure          # 检查全部规则，只重建死掉的
LocalSM tunnel ensure api      # 只管一条
```

`ensure` 逐条对比 pid 是否活着：活着的原样报告，死掉的清掉陈旧 pid 文件后按原规则重
建。它是幂等的，适合挂进定时任务或每次 `LocalSM web` 之前跑一遍。

重建过程中如果 ssh 起不来（比如远端挂了），`ensure` 会把 `tunnels.yaml` 恢复成原样再
抛错——不会因为一次失败就把你的规则定义弄丢。

## 查看状态

```sh
LocalSM tunnel list
LocalSM --json tunnel list | jq -r '.[] | select(.state=="stopped") | .name'
```

`list` 里每条规则带 `state`（`running` / `stopped`）和 `pid`。`state` 只反映 ssh 进程是
否存在，不代表远端服务健康——远端服务挂了，隧道照样是 `running`。

## 与远端扫描的配合

`LocalSM remote scan` 会把每个发现的远端监听端口标注上「已有哪些隧道覆盖它」，所以你
能直接看出哪些端口还没转发。见[远端扫描](remote.md)。

## 删除

```sh
LocalSM tunnel rm api
```

`rm` 向进程组发 `SIGTERM`、删 pid 文件、从 `tunnels.yaml` 里摘掉这条规则。规则被删
后 `ensure` 自然不会再重建它。
