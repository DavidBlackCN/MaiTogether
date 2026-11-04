# 源码构建与维护

MaiTogether 跟进 MaiBot 官方正式稳定版。`baseline.json` 记录当前已验证的版本，不能只改版本号就给新版安装旧补丁。安装和配置见 [README](../README.md) 与[配置说明](setup.md)。

## 文件位置

| 位置 | 内容 |
| --- | --- |
| `host/`、`adapter/` | 新增模块，不是完整安装目录 |
| `patches/series.json` | 每组补丁负责的官方文件、新增模块和依赖 |
| `patches/host/common.patch` | Host、Runner 之间的可信调用信息 |
| `patches/host/behavior.patch`、`patches/adapter/behavior.patch` | 发送检查、结果记录与安全 Hook 处理 |
| `patches/host/sleep.patch` | 睡眠时暂停聊天生成，过滤自动记忆 |
| `baseline.json`、`locks/` | 官方提交与各构建组合的文件校验值 |
| `tools/`、`tests/` | 构建、升级、测试和备份工具 |

真实账号配置、数据库、日志、环境和内部测试报告不进入源码仓库。官方文件的具体修改位置见[补丁边界](patches.md)。

## 从源码构建

构建工具需要 Python 3.11 或以上版本、Git，以及包含固定提交的官方 Host、QQ 连接器 Git 仓库。运行和联调 Host 1.3.19 需要 Python 3.12 或以上版本，本项目在 Python 3.13 环境验收。在本项目目录执行，路径按实际位置替换：

```bash
python tools/build.py --host-source ../upstream/MaiBot --adapter-source ../upstream/MaiBot-SnowLuma-Adapter --output ../control-build
```

输出目录必须不存在。脚本从 Git 提交提取源码，逐组检查并应用补丁，再校验全部文件；不会使用上游目录里尚未提交的改动。输出包含完整的 `host/`、`adapter/` 和构建清单。依赖按固定版本另行安装，来源见 [SOURCES.md](../SOURCES.md)。

默认构建 `full`，保留完整的睡眠和发送约束。维护测试也支持 `--profile behavior`（只控制发送）或 `--profile sleep`（只暂停睡眠期间的聊天与自动记忆，连接器保持官方原版）。两者都依赖 `common`，不能直接删掉共用补丁。

独立组合用于分开维护和测试，不应直接覆盖完整运行实例来切换功能。只控制发送不会节省睡眠期间的聊天生成；只暂停聊天不能约束第三方插件自行发出的 QQ 动作。日常使用保留默认完整组合。

## 跟进官方稳定版

先在三个官方 Git 源码目录中运行 `git fetch origin --tags`，准备好新 SDK 所需的 Python 环境。下面命令均在 MaiTogether 目录执行；候选目录必须不存在。

```bash
python tools/upgrade.py check --host-source ../upstream/MaiBot --sdk-source ../upstream/maibot-plugin-sdk --adapter-source ../upstream/MaiBot-SnowLuma-Adapter --output ../upgrade-candidate
python tools/validate.py --candidate ../upgrade-candidate --workspace ..
python tools/upgrade.py promote --candidate ../upgrade-candidate
```

1. `check` 查询三个项目的最新正式 Release，固定提交，列出发生变化的官方接入文件，尝试构建全部组合。冲突报告指出补丁组和文件；当前基线及运行实例不变。
2. 阅读上游改动和冲突报告，确认调用参数、返回结果、生命周期没有改变。即使补丁能自动应用，也不能跳过这一步。`validate` 检查 SDK 版本、构建文件和测试源码，运行原生 Host、社区插件、连接器及核心插件回归。
3. `promote` 只接受完整通过且仍与源码一致的结果，再确认没有出现更新的正式版，随后更新 `baseline.json` 和六份文件校验清单。它不部署、不覆盖实例。

测试或维护源码改变后，旧结果作废，需要新建候选目录重新验证。上游有冲突时，只调整对应补丁或适配模块；不要把无关官方业务代码复制到项目里。旧版官方源码目录可保留，便于定位差异和回滚。

## 隔离回归的准备

联合测试需要 Super MaiMai 工作区布局：同级的 Vita、Hush、Identity、Coordinate 源码，以及 `.implementation/vendor/smart_poke_plugin`、`.implementation/vendor/Cateye-audit` 中的固定社区源码。版本见来源说明。Python 环境需安装 Host、SDK、核心插件测试依赖；SDK 必须与候选版本一致。

`validate.py` 会测试默认组合及两个独立组合，实际加载 Host、Runner、SDK 和原版社区插件。QQ、模型使用本地替身，测试进程禁止外网连接。结果和日志保存在候选目录，不混入本仓库。

单独定位问题时可运行：

```bash
python tools/run_native.py --workspace .. --host ../control-build/host --adapter ../control-build/adapter
python tools/run_native.py --community --workspace .. --host ../control-build/host --adapter ../control-build/adapter
python tools/run_native.py --sleep --workspace .. --host ../control-build/host --adapter ../control-build/adapter
```

当前原生验收在 Windows 上执行。真实 QQ、SnowLuma、Linux 服务器和长期运行仍需另测；替身不验证真实模型的工具选择和生成质量。

### Vita 生活页面与聊天频率

这组测试还需要工作区 `tools/vita_next_native.py`、[固定版本日期插件](calendar.md)的源码（放在 `.implementation/vendor/date_context_plugin`），以及官方 `maibot-dashboard==1.9.13`、`cnlunar==0.2.4`、`chinese-calendar`、`playwright` 和 Chromium。不需要另行编译前端。

```bash
python tools/run_native.py --vita-next --workspace .. --browser /path/to/chromium
```

它会启动真实 WebUI 和 Runner，实际操作三个页面、睡眠与唤醒、生成参考计划、保存配置，并检查群聊倍率及卸载恢复。测试使用真实的一分钟决策冷却，通常需要数分钟。浏览器及模型只访问本机替身，测试账户与配置临时生成。

进程成功退出后才生成 `acceptance.json`；单独存在 `result.json` 不代表整组通过。`sources.json` 记录参测文件哈希，页面截图与日志保留在同一临时目录。

## 修改补丁与打包

新增逻辑优先放 `host/` 或 `adapter/`。官方代码保留明确的调用位置，不使用运行时替换方法来隐藏改动。`patches/series.json` 是修改范围清单；超出清单的官方文件修改会被导出工具拒绝，需要先审查其必要性。

```bash
python tools/export_patches.py --host-source ../upstream/MaiBot --adapter-source ../upstream/MaiBot-SnowLuma-Adapter --host-working ../working/host --adapter-working ../working/adapter --output ../rebuilt
```

导出后必须重新构建并回归。该命令更新补丁和校验值，本身不证明功能正确。`tools/package.py` 可从工作区打包完整源码和核心插件，要求核心插件仓库干净；Coordinate 使用 Vita 仓库中的同步版本。

## 备份和恢复

先停止 Host 及 Runner。`install.py` 自动备份受影响的源码，但不能替代配置、数据和环境备份。完整备份可用：

```bash
python tools/snapshot.py --code ../control-build/host --runtime ../instance --snapshot ../backup-before-update
python tools/snapshot.py --snapshot ../backup-before-update --restore-to ../restored-instance
```

快照包含代码和实例的 `config/`、`data/`、`plugins/`，检查文件哈希及 SQLite 完整性；其他位置的数据和 Python 环境需另行备份。恢复只写入新目录，确认后再切换实例，并使用匹配的代码、配置、数据和依赖。回到原版 Host 时，同时停用依赖本项目约束的自动行为。
