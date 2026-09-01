# 安装

LocalSM 只支持 macOS：它依赖 `launchd`、`osascript` 和 macOS 的终端应用。

## 推荐：npm 直接安装

需要 Node.js 18 或更高版本：

```sh
npx @shendeguize/local-sm init
npx @shendeguize/local-sm status
```

npm 包内置匹配版本的 LocalSM wheel，不依赖 LocalSM 发布到 PyPI。首次运行时，
启动器发现系统里没有 `uv` 会用 Astral 官方安装脚本装好它，随后由 `uv` 创建隔离
环境并安装运行时依赖。包内也带了同样功能的安装脚本，但新版 npm 默认拦截
lifecycle scripts，所以实际生效的通常是启动器自身的检查。

想要一个短命令，可以全局安装：

```sh
npm install -g @shendeguize/local-sm
LocalSM --version
```

## 开发者：uv 全局安装

从源码开发时需要 Python 3.12+ 和 [uv](https://docs.astral.sh/uv/)：

```sh
uv tool install --editable . --force
LocalSM --version
```

## 项目内运行

不安装全局命令：

```sh
./LocalSM status
uv run python -m localsm.cli status
```

首次运行 `uv` 会创建 `.venv` 并安装依赖。运行时依赖只有 Flask 和 PyYAML。

## 配置放在哪

无论用哪种方式安装，LocalSM 都从同一个位置读配置：

```text
~/.config/localsm/         配置
~/.local/state/localsm/    运行状态
```

这与 LocalSM 自身装在哪里无关——早期版本从安装目录推导路径，在 wheel 安装下会
指向 `uv` 缓存里的临时路径。想把配置和状态都留在仓库内开发，设
`LOCALSM_ROOT="$PWD"`。详见[配置参考](configuration.md)。

## shell 补全

补全脚本由 parser 实时生成，不会与命令脱节：

```sh
# zsh
LocalSM completion zsh > "${fpath[1]}/_LocalSM"

# bash（写进 ~/.bashrc）
source <(LocalSM completion bash)
```

补全会调用 `LocalSM completion services` 取真实服务名，所以新增服务后无需重新
生成脚本。

## 验证安装

```sh
LocalSM doctor --local-only
```

`doctor` 会检查依赖命令、Python 依赖、配置文件和状态目录可写性。缺少配置会被报
为 `FAIL` 并指向 `LocalSM init`。
