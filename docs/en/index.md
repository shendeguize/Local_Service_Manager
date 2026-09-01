# LocalSM documentation

LocalSM is a console for local services and SSH resources on macOS. You write
each local service down as a command template; LocalSM takes care of ports,
logs, process lifecycle, remote listener scans, and SSH tunnels.

中文文档见 [../zh/index.md](../zh/index.md)。

## Getting started

- [Installation](install.md): npm install, uv global install, running from source
- [Quickstart](quickstart.md): from nothing to a running dashboard in five minutes

## Daily use

- [Configuration](configuration.md): file locations, every field, environment variables
- [Services](services.md): start and stop, port allocation, logs, externally supervised services
- [launchd service mode](launchd.md): start at login, and why the port is frozen
- [SSH tunnels](tunnels.md): explicit forwarding rules and self-healing
- [Remote scans](remote.md): probe remote listening ports in parallel
- [Web dashboard](web.md): read-only config view and the security boundary

## Reference

- [CLI reference](cli-reference.md): every command and argument, generated from the parser
- [Output contract](cli-contract.md): JSON shapes and exit codes
- [Architecture](architecture.md): module relationships and the process model
- [Troubleshooting](troubleshooting.md): symptoms and how to narrow them down
