# MaiTogether

一套 MaiBot 插件搭配与配置方案，让麦麦有自己的日常，也能在该休息、该安静的时候停下来。

这里整理选用的插件、配置方法，以及配套的 MaiBot 主程序和 QQ 连接器修改。生活、身份和静音由各插件负责；主程序和连接器在发送前检查状态，减少“已经睡了，却还在戳人或贴表情”的情况。

## 能做什么

- **日常生活**：MaiWeave 提供日程、活动、睡眠和主动交流，让生活经历接上日常聊天。
- **身份与权限**：MaiIdentity 配置固定身份和管理员。亲昵称呼不等于管理权限。
- **保持安静**：MaiHush 管理群静音，配合发送检查约束消息、戳一戳和表情回应。
- **扩展能力**：按需搭配社区插件。已测试的 Smart Poke 和 Cateye 表情回应无需修改源码，就能遵守睡眠和静音限制。

生活和主动交流的设置见 [MaiWeave 配置](docs/maiweave.md)，搜索、回复优化等插件见[插件清单](docs/plugins.md)。

需要处理工作任务时，可使用 [MaiWork 配套适配](integrations/maiwork/README.md)，保留其任务、Agent、Skill 和工作台，并接入生活状态、管理员查询和完整发送回执。

## 快速开始：安装 Host 修改

当前仍处于开发测试阶段。已测试的组合为 **MaiBot 1.3.19 / SDK 2.21.0 / QQ 连接器 1.1.13**，本项目修改版本为 **0.3.2**。

以下命令从**已有的官方 MaiBot 1.3.19 Git 源码**继续，只安装主程序修改，不安装生态插件。需要 Git；MaiBot 的 Python 环境和 SDK 保持上述版本。其他版本请先按官方方式升级，压缩包源码可参考[源码构建](docs/maintenance.md#从源码构建)。

先停止 MaiBot 和插件进程，备份现有源码、配置与数据。下载本项目到独立目录，不要放进 MaiBot 的插件目录。下面示例中，MaiBot 与 MaiTogether 位于同一父目录。

在 MaiBot 的父目录获取本项目：

```bash
git clone https://github.com/DavidBlackCN/MaiTogether.git
cd MaiTogether
```

### Windows（PowerShell）

在 MaiTogether 目录运行，将 `../MaiBot` 改成你的主程序路径：

```powershell
python tools/install.py --host "../MaiBot"
python tools/install.py --host "../MaiBot" --apply
```

### Linux（Bash）

在 MaiTogether 目录运行：

```bash
python3 tools/install.py --host ../MaiBot
python3 tools/install.py --host ../MaiBot --apply
```

第一条命令只检查；第二条会重新检查、备份受影响的源码，再安装。版本不符、源码有改动或新增模块已存在时会停止。备份路径会显示在结果中，可用 `--backup 路径` 指定。写入失败时会恢复本次已修改的文件。

### 安装后

命令只修改主程序源码，不改配置、数据库或现有插件。安装成功后可按原方式启动 MaiBot；源码中出现补丁修改和新增模块是正常现象，不要直接用 Git 丢弃它们。

**装好 Host 不等于已经启用行为控制。** 没有控制配置时，新增检查默认关闭。要约束 QQ 消息、戳一戳和表情回应，还需配套的修改版 QQ 连接器、状态插件和管理范围配置，见[安装与配置](docs/setup.md)；插件选择见[插件清单](docs/plugins.md)。

若安装报错，先确认源码恢复完整再启动。以后升级 MaiBot 时使用对应稳定版的补丁；维护者可按[升级流程](docs/maintenance.md#跟进官方稳定版)检查新版本、构建并运行回归测试。当前验证使用真实主程序和插件、本地模拟 QQ 与模型，尚未完成真实 QQ、SnowLuma 客户端和 Linux 服务器运行验证。

## 使用前了解

- **生活和静音检查针对配置中列出的会话**，插件自身范围也要对应设置。开启控制后，未知动作和敏感读取默认拒绝，群管理操作另需明确授权。
- 睡眠时保留原始消息记录，暂停受管会话的聊天思考与回复生成；醒来不补回睡眠期间的消息。这些记录不会自动作为聊天经历写入记忆。
- 检查失败或必要插件不可用时，暂停相关发送，避免在状态不明时继续行动。
- MaiWeave 当前的状态接口尚不能区分部分空闲时段与唤醒后的回睡间隙，遇到这种情况会暂停对话和主动行为，详见[生活状态限制](docs/maiweave.md#当前规则)。
- 保护范围是 MaiBot 的标准消息发送和官方 QQ 连接器。插件自行联网、QQ 空间及其他外部工具不受这套检查统一管理。
- 发送超时可能意味着结果不明，不能据此认定“没发出去”并立即重发。

## 文档

- [插件清单](docs/plugins.md)：各插件的用途和选用状态。
- [安装与配置](docs/setup.md)：安装顺序、配置字段和常见问题。
- [源码构建与维护](docs/maintenance.md)：构建、测试、备份和目录说明。
- [来源与许可证](SOURCES.md)：上游项目及本项目的修改范围。

本项目基于社区项目开发，并非 MaiBot 官方发行版。固定源码版本见 [baseline.json](baseline.json)。
