# 源码维护

普通安装见[安装与设置](setup.md)。本页供维护者更新补丁、构建和测试。

当前配套使用 Host 1.4.3、SDK 2.22.1、QQ 连接器 1.1.13，MaiTogether 修改版本为 0.6.0。准确提交见 [baseline.json](../baseline.json)。

## 目录

| 位置 | 内容 |
| --- | --- |
| `host/`、`adapter/` | 本项目新增模块，不是完整安装目录 |
| `patches/` | 对官方文件的修改；`series.json` 列出修改范围 |
| `locks/` | 完整 Host 和连接器的两份文件校验清单 |
| `integrations/` | MaiWeave、MaiWork 的固定源码、适配补丁和构建工具 |
| `tools/`、`tests/` | 安装、构建、升级和验证工具 |
| `docs/plugins/` | 每个选用插件的版本、配置和搭配说明 |

运行配置、凭据、数据库、日志和内部验收记录不进入仓库。官方文件修改说明见[补丁范围](patches.md)。

## 从源码构建

需要 Git、Python 3.11 以上版本，以及含固定提交的官方源码仓库。在 MaiTogether 目录执行：

```bash
python tools/build.py --host-source ../upstream/MaiBot --adapter-source ../upstream/MaiBot-SnowLuma-Adapter --output ../control-build
```

输出目录必须不存在，包含完整 `host/`、`adapter/` 和版本记录。工具从固定 Git 提交读取源码、应用补丁并核对文件，不使用上游目录里未提交的改动。运行 Host 1.4.3 需要 Python 3.12 以上版本及其依赖。

安装准备工具也支持离线源码：

```bash
python tools/prepare.py --host ../MaiBot --adapter-source ../upstream/MaiBot-SnowLuma-Adapter --output ../MaiTogether-ready
```

不加 `--apply` 时只检查 Host 并生成连接器与配置示例，不修改 Host。

## 跟进官方稳定版

先在 Host、SDK、连接器的官方仓库中获取最新标签，再执行：

```bash
python tools/upgrade.py check --host-source ../upstream/MaiBot --sdk-source ../upstream/maibot-plugin-sdk --adapter-source ../upstream/MaiBot-SnowLuma-Adapter --output ../upgrade-candidate
python tools/validate.py --candidate ../upgrade-candidate --workspace ..
python tools/upgrade.py promote --candidate ../upgrade-candidate
```

- `check` 查询最新正式 Host／SDK，并选择声明支持它们的正式连接器版本，记录提交、列出受影响文件并尝试构建，输出在候选目录的 `build/`。
- 检查上游接口变化后运行 `validate`，不能只以补丁能应用为通过。
- `promote` 要求回归通过、源码与结果一致，并再次核对正式版，然后更新版本记录和两份校验清单，不部署运行实例。

有冲突时只修改对应补丁或新增模块。不要为追赶新版本复制一套官方业务代码。维护源码改变后，应重新建立候选目录。

当前连接器 1.3.1 要求尚未正式发布的 Host 1.4.4；1.1.13 的官方安装声明又停在 Host 1.3.x。配套修改版已将 1.1.13 的支持上限更新到经过验证的 Host 1.4.3。本次维护检查在 `check` 命令末尾增加 `--adapter-tag v1.1.13`，仍必须通过组装后的版本检查和完整回归；普通用户的安装命令不变。新 Host 正式发布后重新评估连接器，不沿用这一选择。

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

MaiWeave 完整组合另传 `--maiweave <已构建适配>`；工作联动再加 `--maiwork <已构建适配>`。构建方法分别见 [MaiWeave](../integrations/maiweave/README.md) 和 [MaiWork](../integrations/maiwork/README.md)。两者都会检查来源、补丁和文件哈希。先审查 MaiWeave 当时默认分支最新源码并更新准确提交记录，不把旧版本结果套用到新版本。Host 回归不等于这两项完整组合通过。

同时验证消息后处理与智能分段时，再传 `--post-processing <Cateye源码> --segmentation <智能分段源码>`，测试配置会关闭 Cateye 分段。

可用 `--smart-poke <源码>` 检查新的 Smart Poke 提交。每轮输出都会记录实际参测文件哈希，不用旧版本结果代替新版验收。

进程正常退出后才生成 `acceptance.json`。真实 QQ、SnowLuma 客户端、Linux 服务器及长期运行需另行验证。

## 修改和导出补丁

独立逻辑放在本项目模块，官方代码只留必要调用。导出工具拒绝 `patches/series.json` 之外的官方文件改动：

```bash
python tools/export_patches.py --host-source ../upstream/MaiBot --adapter-source ../upstream/MaiBot-SnowLuma-Adapter --host-working ../working/host --adapter-working ../working/adapter --output ../rebuilt
```

导出会更新补丁和校验值，随后重新回归。可用 `tools/package.py` 打包源码；它要求核心插件仓库干净，并检查可选 MaiWeave、MaiWork 的版本记录。MaiWork 组合尚未匹配当前 Host 时不能强行打包。

## 更新与恢复

社区插件按各自页面和上游说明更新，不必因此重新安装 Host。Host 和配套 QQ 连接器则一起更新，不用市场原版覆盖修改版连接器。

更新主程序时先停机备份，准备对应官方版本的源码、应用匹配的 MaiTogether 修改，再使用原 Bot 实例目录启动。不要在旧补丁上反复覆盖新补丁，也不要把运行配置和数据复制进源码仓库。依赖按目标 Host 更新。

`install.py` 和 `prepare.py --apply` 会备份受影响源码，备份路径打印在终端。配置、插件数据和 Python 环境仍需另行备份。完整代码与实例快照可用：

```bash
python tools/snapshot.py --code ../MaiBot --runtime ../instance --snapshot ../backup-before-update
python tools/snapshot.py --snapshot ../backup-before-update --restore-to ../restored-instance
```

恢复只写新目录，确认后再切换。代码、连接器、配置、数据和依赖应来自同一次可用组合。切回原版 Host 时，依赖统一控制的自动行为应同时停用。
