# LocalSM

LocalSM 是一个面向 macOS 的本地服务与 SSH 资源控制台。它把
`enva`、`dshc`、`aqp`、`kimi`、`dsh` 等服务统一成可配置的命令模板，
同时管理端口、日志、远端监听扫描和 SSH 隧道。

LocalSM 没有常驻 supervisor：服务以 detached 进程运行，用 pidfile、端口
探测和日志记录状态。这样即使 LocalSM 退出，已启动的服务也不会被自动杀掉。

## 安装

### 推荐：uv 全局安装

需要 Python 3.12+ 和 [uv](https://docs.astral.sh/uv/)：

```sh
uv tool install --editable . --force
LocalSM --version
```

editable 安装会让全局命令继续使用仓库内的 `config/` 和 `state/`。

### npm 启动器

如果已安装 `uv`，也可以通过 npm 启动器运行已发布的 Python CLI：

```sh
npx @shendeguize/local-sm --version
```

该 npm 包是轻量包装器，不会捆绑 Python；完整说明见
[`packages/npm/README.md`](packages/npm/README.md)。
版本发布流程见 [`docs/releasing.md`](docs/releasing.md)。

### 项目内使用

不安装全局命令，直接运行：

```sh
./LocalSM status
uv run python -m localsm.cli status
```

首次运行 `uv` 会创建 `.venv` 并安装依赖。运行时依赖只有 Flask 和
PyYAML，测试依赖通过 `uv sync --dev` 安装。

## 快速上手

```sh
# 查看当前配置和状态
LocalSM config
LocalSM status

# 启动 Web 控制台
LocalSM web
# 浏览器打开 http://127.0.0.1:8765/

# 启动单个服务；端口冲突时自动从端口池选择
LocalSM up enva --auto-port
LocalSM restart enva
LocalSM logs enva
LocalSM down enva
```

Web 页面提供服务启停、重启、改端口、日志抽屉、远端扫描、SSH 终端和
隧道管理。所有 API 操作失败都会显示后端错误，不需要查看终端日志。

## CLI 参考

```text
LocalSM --version
LocalSM up [SERVICE] [--port PORT] [--auto-port]
LocalSM down [SERVICE]
LocalSM restart [SERVICE] [--port PORT] [--auto-port]
LocalSM status [SERVICE]
LocalSM set-port SERVICE PORT
LocalSM exec SERVICE COMMAND...
LocalSM logs SERVICE [--lines N]
LocalSM config
LocalSM doctor [--local-only] [--timeout SECONDS]
LocalSM remote scan [HOST...] [--timeout SECONDS]
LocalSM tunnel add NAME HOST LOCAL_PORT REMOTE_PORT [--remote-host HOST]
LocalSM tunnel rm NAME
LocalSM tunnel list
LocalSM tunnel ensure [NAME]
LocalSM ssh HOST [--app ghostty|terminal]
LocalSM web
```

不指定 `SERVICE` 时，`up`、`down`、`restart`、`status` 会作用于全部服务。
`exec` 使用参数列表直接执行命令，不会替换受管服务进程：

```sh
LocalSM exec enva pwd
LocalSM logs kimi --lines 120
LocalSM set-port aqp 18080
```

`doctor` 默认会扫描 SSH config 中的 Host；网络受限时可用
`LocalSM doctor --local-only` 只检查本机。

## 远端扫描与隧道

```sh
LocalSM remote scan
LocalSM tunnel add api-pod my-pod 18080 8080
LocalSM tunnel list
LocalSM tunnel ensure api-pod
LocalSM tunnel rm api-pod
LocalSM ssh my-pod --app ghostty
```

扫描按需并行执行，远端端口探测按 `ss`、`lsof`、`netstat`、`/proc` 顺序
降级。LocalSM 只读取 `~/.ssh/config`，不会向其中写入 `LocalForward`。
隧道规则在 `config/tunnels.yaml` 中维护。

## 配置

服务配置示例：

```yaml
port_pool: [8000, 8999]
services:
  enva:
    start: "enva serve -p {port}"
    preferred_port: 8080
  dshc:
    start: "dshc up --port {port}"
    set_port:
      - "dshc config set manager.port {port} --port {current_port}"
      - "dshc restart --port {current_port}"
```

完整字段、环境变量和 state 布局见
[docs/configuration.md](docs/configuration.md)，系统设计见
[docs/architecture.md](docs/architecture.md)。

## 自检、测试与 smoke

```sh
make install       # uv tool editable 安装
make doctor        # 本机 + SSH Host 检查
make test          # pytest + 75% 覆盖率门禁
make cov           # 生成 htmlcov/
make smoke         # 全量真实服务验收，可能改变服务状态
```

密封单测不会连接真实 SSH 或启动真实 CLI。`scripts/smoke.sh` 才会执行
全量真实验收；它会尽力恢复 dshc 的原端口和 launchd 状态。执行前请确认
当前服务状态允许被重启。

README.md 与 README.en.md 的上述一级章节需要保持同步；新增用户可见功能
时请同时更新两份文档。CI 会检查章节结构和本地链接。

## 路线图

- npm 启动器：已提供 `@shendeguize/local-sm`，依赖用户侧安装的 `uv`。
- launchd 原生服务模板：当前只管理 detached 进程，后续可按服务选择系统托管。
- 远端扫描结果 diff 与通知：当前提供按需扫描和缓存。
