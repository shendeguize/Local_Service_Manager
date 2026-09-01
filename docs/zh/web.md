# Web 面板

面板是 LocalSM 的操作台：一屏看到所有服务的状态、端口、日志，一键启停，以及远端扫描
结果和隧道管理。它不是配置编辑器——服务定义在面板里是只读的。

## 启动

```sh
LocalSM web                # 后台起，作为一个普通 LocalSM 服务
LocalSM web --foreground   # 在当前终端跑，Ctrl-C 停止
```

默认地址 `http://127.0.0.1:8765/`。`web` 本身也是 `services.yaml` 里的一个服务（`init`
生成的模板里就有），所以 `LocalSM status`、`LocalSM logs web`、`LocalSM enable web` 对
它一样有效。

`--foreground` 适合调试面板本身，或者你想要一个「关掉终端就停」的临时面板。

## 安全模型

面板**永久无鉴权**，靠三层边界保证安全：

1. 只监听 `127.0.0.1`，不接受局域网连接
2. 校验 `Host` 请求头，只回应 loopback 名字（`127.0.0.1`、`localhost`、`::1`）
3. 需要远程访问时，走 SSH 隧道，而不是把它暴露出去

不加登录页是有意的：这是一个单用户的本机工具，加密码只会带来一份要维护的凭据，而挡不
住任何能在你机器上跑代码的人。

### Host 头校验挡的是什么

面板的 API 能启动进程，等于本机上的代码执行能力。仅绑定 loopback 挡不住 DNS
rebinding：攻击者控制一个域名，让它解析到 `127.0.0.1`，你的浏览器就会带着攻击者页面
的 JavaScript 去请求你的面板。绑定地址在这个过程中是满足的——请求真的来自本机。

校验 `Host` 头把这条路封死了：浏览器发出的 `Host` 是攻击者的域名，不是 loopback 名
字，请求直接 403。

想让面板回应其他名字（比如你有个指向 127.0.0.1 的本地 hosts 别名）：

```sh
LOCALSM_WEB_ALLOWED_HOSTS=dev.local,box.internal LocalSM web
```

多个名字用逗号分隔。这是显式的白名单，不影响绑定地址仍然是 loopback。

## 界面分区

- **服务**：状态、pid、端口、URL、`managed_by`；启停重启、改端口、拉日志抽屉
- **配置**：来自 `/api/config` 的只读视图——配置文件路径、端口池、每个服务的
  `start` 与 `working_dir`。想改就用 `LocalSM edit`
- **远端**：`remote_scan.json` 缓存里的主机与监听端口，附带隧道覆盖情况，可以直接
  重扫或对未覆盖端口建隧道
- **隧道**：规则列表与状态，新建、删除、`ensure` 重建
- **SSH**：对任一主机开终端窗口

## 配置热感知

面板不需要为了看到新服务而重启。每次请求都会检查 `services.yaml` 的 mtime 与大小，变
了就重建 ServiceManager。所以流程是：

```sh
LocalSM edit        # 改配置，保存退出
```

前端 5 秒一次的自动刷新周期到了，新服务就出现在面板里。

只监听 `services.yaml` 而不是整个配置目录，是因为服务定义是面板唯一需要热感知的东西；
隧道规则每次请求都是现读的。

## API

面板前端用的就是这套 HTTP API，脚本也可以直接调，全部路径都受 Host 头校验保护：

| 方法与路径 | 作用 |
| --- | --- |
| `GET /api/services` | 全部服务状态 |
| `POST /api/services/<名字>/<动作>` | `up` / `down` / `restart` / `set-port` |
| `GET /api/config` | 只读配置视图 |
| `GET /api/logs/<名字>?lines=N` | 日志尾部，N 上限 500 |
| `GET /api/remote` | 上次扫描结果与时间 |
| `POST /api/remote/scan` | 触发扫描 |
| `GET /api/tunnels` | 隧道列表与状态 |
| `POST /api/tunnels` | 新建隧道 |
| `POST /api/tunnels/ensure` | 重建死掉的隧道 |
| `DELETE /api/tunnels/<名字>` | 删除隧道 |
| `POST /api/ssh/<主机>` | 打开 SSH 终端窗口 |

服务与隧道操作失败会返回 400 与 `{"error": "..."}`。写脚本的话，CLI 的 `--json` 输出
是更稳定的接口，见[输出契约](cli-contract.md)。

## 远程访问

需要在别的机器上看面板，就转发它，而不是改绑定地址：

```sh
# 在远端机器上
ssh -N -L 8765:127.0.0.1:8765 你的-mac
```

然后在那台机器上打开 `http://127.0.0.1:8765/`——`Host` 是 loopback 名字，校验通过。
