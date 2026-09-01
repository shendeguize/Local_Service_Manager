# 远端扫描

远端扫描回答一个问题：我 SSH 配置里那些主机上，现在有什么在监听？这是给 SSH 到一堆
开发机、pod、跳板机后面的机器的人用的——不用逐台登进去敲 `ss -ltn`。

## 用法

```sh
LocalSM remote scan                  # 扫 ssh config 里所有主机
LocalSM remote scan pod-a pod-b      # 只扫指定的几台
LocalSM remote scan --timeout 15
LocalSM --json remote scan
```

结果同时写进 `~/.local/state/localsm/remote_scan.json`，Web 面板读的是这份缓存，所以
面板打开时不会现场重扫一遍。

## 主机从哪来

LocalSM 解析 `~/.ssh/config`，取 `Host` 块的别名，并记下 `HostName`、`Port`、`User`、
`ProxyJump`。含通配符的别名（`*`、`?`、`!`）会被跳过——`Host *` 是一组默认配置，不是
一台能连的机器。

LocalSM 不重新实现 SSH 的连接逻辑：它只是用别名调 `ssh`，跳板机、密钥、端口都由 SSH
自己按你的配置处理。所以只要 `ssh my-pod` 能通，扫描就能通。

## 扫描怎么做的

对每台主机，LocalSM 通过一次 SSH 执行一段探测脚本，按可用性依次尝试：

1. `ss -ltnH`（现代 Linux）
2. `lsof -nP -iTCP -sTCP:LISTEN`（macOS 与老 Unix）
3. `netstat -lnt`
4. 读 `/proc/net/tcp` 与 `/proc/net/tcp6` 的 Python 兜底

四种都没有才报错退出。这个降级链是为了让扫描在精简容器里也能工作——很多 pod 镜像既
没有 `ss` 也没有 `netstat`，但几乎总有 `python3`。

连接参数固定为 `BatchMode=yes`（绝不交互式要密码，否则并发扫描会卡住等你输入）、
`ConnectTimeout`（默认 8 秒，`--timeout` 可调）和 `StrictHostKeyChecking=accept-new`
（首次连接自动接受主机密钥，但密钥变了仍会拒绝）。

主机之间并行扫，最多 12 个并发。

## 读结果

每台主机一条记录：

| 字段 | 含义 |
| --- | --- |
| `host` | ssh config 里的别名 |
| `reachable` | 能否连上并完成探测 |
| `ports` | 发现的监听端口，去重排序 |
| `tunnels` | 端口到覆盖它的隧道名列表的映射 |
| `error` | 失败原因，成功时为 `null` |

`tunnels` 字段是这个功能真正有用的地方：它把「远端有什么」和「我本机已经转了什么」对
上了，所以未覆盖的端口一眼可见：

```sh
LocalSM --json remote scan \
  | jq -r '.[] | . as $h | .ports[] | select(($h.tunnels[tostring] | length) == 0) | "\($h.host):\(.)"'
```

## reachable 与 error 的区别

失败分两类，LocalSM 有意区分：

- 网络层失败（连接超时、拒绝、域名解析不了、认证被拒）→ `reachable: false`
- 连上了但探测命令失败（比如四种探测工具都没有）→ `reachable: true`，`error` 里写原因

这个区分让你知道该修 SSH 配置还是该修远端环境。

## 在面板里

Web 面板的远端区域展示同一份数据，每个端口旁边显示隧道覆盖情况，可以直接对未覆盖的
端口建隧道。见 [Web 面板](web.md)与[SSH 隧道](tunnels.md)。

## 打开 SSH 会话

扫完想直接登进去看看：

```sh
LocalSM ssh my-pod              # 默认 Ghostty
LocalSM ssh my-pod --app terminal
```

这会在终端应用里开一个新窗口/标签跑 `ssh my-pod`，不占用当前 shell。
