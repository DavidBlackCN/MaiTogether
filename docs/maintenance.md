# 源码维护

普通安装见[安装与设置](setup.md)。本页供维护者更新补丁、构建和测试。

Host、SDK、连接器和 MaiTogether 的配套版本及准确提交见 [baseline.json](../baseline.json)。

## 目录

| 位置 | 内容 |
| --- | --- |
| `host/`、`adapter/` | 本项目新增模块，不是完整安装目录 |
| `patches/` | 对官方文件的修改；`series.json` 列出修改范围 |
| `locks/` | 完整 Host 和连接器的两份文件校验清单 |
| [社区插件版本](../locks/community-plugins.json) | 打包和联测使用的 MaiWeave、MaiWork 上游提交 |
| `tools/`、`tests/` | 安装、构建、升级和验证工具 |
| `docs/plugins/` | 每个选用插件的版本、配置和搭配说明 |

运行配置、凭据、数据库、日志和内部验收记录不进入仓库。官方文件修改说明见[补丁范围](patches.md)。

## 维护插件文档

在插件清单用一句话写明用途，链接到同名专页。有安装限制时，在插件名旁标出“暂缓安装”“指定分支”或“指定提交”。专页依次写用途、可用的安装入口、必须改的设置、与其他插件搭配时的注意事项。沿用默认配置的插件一段即可。完整配置由上游维护，这里只列本组合实际需要的字段。

## 从源码构建

需要 Git、Python 3.11 以上版本，以及含固定提交的官方源码仓库。在 MaiTogether 目录执行：

```bash
python tools/build.py --host-source ../upstream/MaiBot --adapter-source ../upstream/MaiBot-SnowLuma-Adapter --output ../control-build
```

输出目录必须不存在，包含完整 `host/`、`adapter/` 和版本记录。工具从固定 Git 提交读取源码、应用补丁并核对文件，不使用上游目录里未提交的改动。运行 Host 1.4.8 需要 Python 3.12 以上版本及其依赖。

安装准备工具也支持离线源码：

```bash
python tools/prepare.py --host ../MaiBot --adapter-source ../upstream/MaiBot-SnowLuma-Adapter --output ../MaiTogether-ready
```

此模式只检查 Host，并导出连接器与配置示例。可重复使用内容与本版一致的导出目录。只安装 Host 可用 `python tools/install.py --host ../MaiBot --apply`。普通安装要在脚本中传入账号和群号时，可给快速开始命令加 `--account 123456789 --groups 987654321 876543210`。

## 跟进官方稳定版

先在 Host、SDK、连接器的官方仓库中获取最新标签，再执行：

```bash
python tools/upgrade.py check --host-source ../upstream/MaiBot --sdk-source ../upstream/maibot-plugin-sdk --adapter-source ../upstream/MaiBot-SnowLuma-Adapter --output ../upgrade-candidate
python tools/validate.py --candidate ../upgrade-candidate --workspace .. --maiweave ../.implementation/vendor/MaiWeave
python tools/upgrade.py promote --candidate ../upgrade-candidate
```

- `check` 查询最新正式 Host／SDK，并选择声明支持它们的正式连接器版本，记录提交、列出受影响文件并尝试构建，输出在候选目录的 `build/`。
- 检查上游接口变化后运行 `validate`，不能只以补丁能应用为通过。
- `promote` 要求回归通过、源码与结果一致，并再次核对正式版，然后更新版本记录和两份校验清单，不部署运行实例。

有冲突时只修改对应补丁或新增模块。不要为追赶新版本复制一套官方业务代码。维护源码改变后，应重新建立候选目录。


## 回归环境

准备同级的 `maibot-maihush-plugin`、`maibot-maiIdentity-plugin`，以及工作区 `.implementation/vendor/smart_poke_plugin`、`.implementation/vendor/Cateye-audit` 中的原版社区源码。Python 环境安装 Host、SDK、插件及测试依赖，SDK 与候选版本一致。

验证加载真实 Host、Runner 和插件，QQ 与模型使用本地替身，外网连接被禁止。生活状态由隔离测试插件提供。单独运行某类场景：

```bash
python tools/run_native.py --workspace .. --host ../control-build/host --adapter ../control-build/adapter
python tools/run_native.py --community --workspace .. --host ../control-build/host --adapter ../control-build/adapter
python tools/run_native.py --native-chat --workspace .. --host ../control-build/host --adapter ../control-build/adapter
python tools/run_native.py --life-provider --workspace .. --host ../control-build/host --adapter ../control-build/adapter
```

`--native-chat` 检查消息仍进入官方聊天、记忆处理入口，同时睡眠会阻止对外动作。它不验证真实模型的理解与生成效果。

联测时传入 `--maiweave <原版源码目录>` 和可选的 `--maiwork <原版源码目录>`。加 `--maiweave-smoke` 可用未经测试探针改写的 MaiWeave 检查加载与公开 API。MaiWork 始终使用原版。升级时先审查上游最新提交，更新 [社区插件版本](../locks/community-plugins.json)，再用干净检出运行联测。MaiWeave 上游接口测试可用 `python tools/test_maiweave.py --source <原版源码目录> --output <新目录>` 单独运行。

同时验证消息后处理与智能分段时，再传 `--post-processing <Cateye源码> --segmentation <智能分段源码>`，测试配置会关闭 Cateye 分段。

可用 `--smart-poke <源码>` 检查新的 Smart Poke 提交。每轮输出都会记录实际参测文件哈希，不用旧版本结果代替新版验收。

进程正常退出后才生成 `acceptance.json`。真实 QQ、SnowLuma 客户端、Linux 服务器及长期运行需另行验证。

## 修改和导出补丁

独立逻辑放在本项目模块，官方代码只留必要调用。导出工具拒绝 `patches/series.json` 之外的官方文件改动：

```bash
python tools/export_patches.py --host-source ../upstream/MaiBot --adapter-source ../upstream/MaiBot-SnowLuma-Adapter --host-working ../working/host --adapter-working ../working/adapter --output ../rebuilt
```

导出会更新补丁和校验值，随后重新回归。`tools/package.py` 可用 `--maiweave-source` 和 `--maiwork-source` 将审查过的原版源码随包分发。

## 实例快照

先停止 Host 和 Runner，将备份写到源码和实例目录之外。用户更新与恢复见[实例设置](setup.md#更新与恢复)。

```bash
python tools/snapshot.py --code ../MaiBot --runtime ../instance --snapshot ../backup-before-update
python tools/snapshot.py --snapshot ../backup-before-update --restore-to ../restored-instance
```

恢复只写新目录，确认后再切换。代码、连接器、配置、数据和依赖应来自同一次可用组合。切回原版 Host 时，依赖统一控制的自动行为应同时停用。
