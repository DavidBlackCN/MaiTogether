# 源码构建与维护

这份文档供需要构建或修改源码的人使用。安装和日常配置见[安装与配置](setup.md)。

## 文件位置

| 位置 | 内容 |
| --- | --- |
| `docs/` | 插件选用、安装配置和维护说明 |
| `behavior_control.example.json` | 不含真实账号的配置示例 |
| `host/`、`adapter/` | 新增的主程序和连接器源码；不是完整安装目录 |
| `patches/` | 对官方现有文件的修改 |
| `baseline.json` | 固定的官方版本和提交 |
| `locks/` | 构建产物的文件校验值 |
| `tools/`、`tests/` | 构建、测试和备份工具 |
| `licenses/` | 上游许可证 |

可公开的插件清单和配置示例随本项目维护。真实账号配置、数据库、日志、环境和内部开发记录不放入项目源码。

## 从源码构建

需要 Python 3.11 或以上版本、Git，以及包含 [baseline.json](../baseline.json) 中固定提交的官方 Host、QQ 连接器 Git 仓库。不要直接给新版源码套用旧补丁。

在本项目目录运行，将示例路径替换为你的路径：

```powershell
python tools/build.py --host-source ../upstream/MaiBot --adapter-source ../upstream/MaiBot-SnowLuma-Adapter --output ../control-build
```

输出目录必须不存在。脚本从固定 Git 提交提取源码、应用修改，并核对每个文件的校验值；不会使用上游仓库中尚未提交的改动。成功后得到完整的 `host/` 和 `adapter/`。

构建不包含依赖安装。运行时还需安装 Host 依赖及固定提交的 SDK 2.21.0，来源见 [SOURCES.md](../SOURCES.md)。

## 隔离测试

当前联合测试工具依赖 Super MaiMai 工作区布局，不能只下载本目录就直接运行。需要准备：

- 与本目录同级的 Vita、Hush、Identity、Coordinate 源码目录。
- `.implementation/vendor/smart_poke_plugin` 和 `.implementation/vendor/Cateye-audit` 中的固定社区源码，版本见来源说明。
- 已安装 Host、SDK 和插件依赖的 Python 环境，以及构建好的 Host、连接器。

从工作区根目录运行：

```powershell
python MaiTogether/tools/run_native.py --host control-build/host --adapter control-build/adapter
python MaiTogether/tools/run_native.py --community --host control-build/host --adapter control-build/adapter
python MaiTogether/tools/run_native.py --sleep --host control-build/host --adapter control-build/adapter
```

三条命令分别检查整体功能、原版 Smart Poke／Cateye，以及睡眠时的聊天生成和自动记忆。脚本创建独立实例，只连接本地模拟服务并阻断外网。测试实例和结果保存在 `.implementation/behavior-control/`。

这些测试实际加载 Host、Runner、SDK 和插件，但不验证真实模型的工具选择、QQ 账号或 SnowLuma 客户端。当前已有 Windows 隔离测试，Linux 服务器和长期运行仍需另测。

## 修改与打包

新增模块保存在 `host/` 或 `adapter/`，修改官方文件时更新 `patches/`。`tools/export_patches.py` 用于重新生成补丁和校验值。完成后应从干净官方源码重新构建，不能只确认手工修改的实例能运行。

`tools/package.py` 目前也依赖工作区布局，用于打包 Host、连接器、四个配套插件和本目录的维护文件。它要求核心插件仓库没有未提交改动；Coordinate 使用 Vita 仓库中同步保存的版本。源码目录独立发布前，仍需整理这些工作区依赖。

## 备份和恢复

先停止 Host 及所有 Runner，再备份。以下命令在本项目目录执行，路径按实际位置填写，输出目录必须不存在：

```powershell
python tools/snapshot.py --code ../control-build/host --runtime ../instance --snapshot ../backup-before-update
python tools/snapshot.py --snapshot ../backup-before-update --restore-to ../restored-instance
```

工具保存代码和实例中的 `config/`、`data/`、`plugins/`，检查文件校验值和 SQLite 数据库完整性。其他位置的配置、数据和 Python 环境需要另行备份。

恢复命令只复制到新目录，不会自动替换正在使用的实例。恢复时使用相互匹配的代码、配置和数据，并重新准备对应的依赖环境。如果恢复到原版 Host，应同时停用依赖本项目保护的社区自动行为。
