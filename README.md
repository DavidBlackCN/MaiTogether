# MaiTogether

这不是一个 MaiBot 插件，也不是一个单独的项目，而是一套 MaiBot 插件搭配与配置方案，让麦麦有自己的完整日常，也能在该休息、该安静的时候停下来。

这里整理选用的插件、配置方法，以及配套的 MaiBot 主程序和 QQ 连接器修改。生活、身份和静音由各插件负责；主程序和连接器在发送前检查状态，减少“已经睡了，却还在戳人或贴表情”的情况。

## 能做什么

- **日常生活**：MaiWeave 提供日程、活动、睡眠和主动交流，让生活经历接上日常聊天。
- **身份与权限**：MaiIdentity 配置固定身份和管理员。亲昵称呼不等于管理权限。
- **保持安静**：MaiHush 管理群静音，配合发送检查约束消息、戳一戳和表情回应。
- **工作任务**：[MaiWork 配套适配](docs/plugins/maiwork.md)，保留其任务、Agent、Skill 和工作台，并接入生活状态、管理员查询和完整发送回执。
- **扩展能力**：按需搭配社区插件。通过标准发送或配套 QQ 连接器执行的动作，可以共用睡眠和静音检查。

生活和主动交流的设置见 [MaiWeave 配置](docs/plugins/maiweave.md)，搜索、回复优化等插件见[插件清单](docs/plugins.md)。

## 快速开始：安装主程序修改

> 当前适用 **MaiBot 1.4.2**，仍处于开发测试阶段，请在开始操作前备份源码、配置和数据！

以下从已有的官方 MaiBot Git 源码继续，在 MaiBot 的父目录获取本项目：

```bash
git clone https://github.com/DavidBlackCN/MaiTogether.git
cd MaiTogether
```

将下面的 `../MaiBot` 换成主程序路径，输出目录使用一个新目录。

**Windows（PowerShell）：**

```powershell
python tools/prepare.py --host "../MaiBot" --output "../MaiTogether-ready" --apply
```

**Linux：**

```bash
python3 tools/prepare.py --host ../MaiBot --output ../MaiTogether-ready --apply
```

命令会检查版本、准备配套 QQ 连接器，然后备份并安装主程序修改。不会安装生态插件、改写运行配置或数据库。

输出目录中的 `adapter/` 是配套 QQ 连接器，`behavior_control.example.json` 是配置示例。按[安装与设置](docs/setup.md)放入对应 Bot 实例、选择插件并填写账号和群号即可启用。已经安装过主程序修改时，无需因为新增插件重复执行以上命令。

只想安装 Host 源码、不下载连接器时，可用 `python tools/install.py --host ../MaiBot --apply`；Linux 使用 `python3`。版本不同或已有源码改动时，安装器会停止，处理方式见[常见问题](docs/troubleshooting.md)。

## 使用前了解

- 日常生活、聊天与唤醒由 MaiWeave 和 MaiBot 处理；MaiTogether 在发送前检查生活状态、群静音和权限。
- 睡眠时仍可能接收消息、调用模型和形成记忆，不保证模型消耗为零。
- 生活和静音检查作用于配置中指定的会话。必要插件不可用或状态不明确时，会停止相关发送。
- 保护范围是标准消息发送和配套 QQ 连接器。插件自行联网、QQ 空间和其他外部工具需按各自说明管理。
- 超时可能只是没有收到回执，重发前先确认实际结果。

## 文档

- [安装与设置](docs/setup.md)：从现有 MaiBot 开始使用。
- [插件清单](docs/plugins.md)：选择插件，查看各自的配置说明。
- [更多配置](docs/configuration.md)：私聊、多账号和自动行动权限。
- [常见问题](docs/troubleshooting.md)：不回应、版本不符和部分发送的排查。
- [源码维护](docs/maintenance.md)：供维护者构建、升级和测试。
- [来源与许可证](SOURCES.md)。

本项目并非 MaiBot 官方发行版。主程序和连接器的配套版本记录在 [baseline.json](baseline.json)。

## 鸣谢

- [Mai-with-u/MaiBot](https://github.com/Mai-with-u/MaiBot)
- [ilworkcn/MaiWeave](https://github.com/ilworkcn/MaiWeave)
