# LocalSM 文档

LocalSM 是一个面向 macOS 的本地服务与 SSH 资源控制台。你把每个本地服务写成
一份命令模板，LocalSM 负责端口、日志、进程生命周期、远端监听扫描和 SSH 隧道。

English documentation lives in [../en/index.md](../en/index.md).

## 上手

- [安装](install.md)：npm 直接安装、uv 全局安装、源码运行
- [快速上手](quickstart.md)：从零到面板跑起来的五分钟

## 日常使用

- [配置参考](configuration.md)：配置文件位置、全部字段、环境变量
- [服务管理](services.md)：启停、端口分配、日志、外部托管服务
- [launchd 服务模式](launchd.md)：开机自启与端口冻结
- [SSH 隧道](tunnels.md)：显式转发规则与自愈
- [远端扫描](remote.md)：并行探测远端监听端口
- [Web 面板](web.md)：只读配置视图与安全边界

## 参考

- [CLI 参考](cli-reference.md)：全部命令与参数（由 parser 自动生成）
- [输出契约](cli-contract.md)：JSON 形态与退出码约定
- [架构](architecture.md)：模块关系与进程模型
- [故障排查](troubleshooting.md)：常见症状与定位方法
