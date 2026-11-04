# 来源与许可证

本项目基于以下官方源码。构建使用固定提交，完整版本记录见 [baseline.json](baseline.json)。

| 项目 | 版本 | 本项目的处理 |
| --- | --- | --- |
| [MaiBot](https://github.com/Mai-with-u/MaiBot) | 1.3.19 | 检查发送权限和生活状态；睡眠时暂停聊天生成和自动记忆，未发送草稿不进入后续上下文 |
| [Plugin SDK](https://github.com/Mai-with-u/maibot-plugin-sdk) | 2.21.0 | 使用原版，没有修改 |
| [QQ 连接器](https://github.com/Mai-with-u/MaiBot-SnowLuma-Adapter) | 1.1.13 | 在实际发送前再次检查状态，分别处理批量动作的结果 |

社区兼容测试使用原版源码，没有修改：

- [Smart Poke 1.11.1](https://github.com/TAIY2020/smart_poke_plugin/tree/59ff292b4d912a5cbe5d09cce32381e8497d350f)。
- [Cateye 表情回应 0.3.2](https://github.com/cateyemizuki/cateye_set_msg_emoji_like_api_modify/tree/f239878a3eb217fa4730fb9569c2277de4beaa01)。

其他插件的来源见[插件清单](docs/plugins.md)，各自保留原作者和许可证。

## 许可证

Host 上游附 GPL 第 3 版许可证，原文保存在 [licenses/Host-LICENSE](licenses/Host-LICENSE)。

QQ 连接器的固定提交没有单独的 LICENSE 文件，其 Manifest 声明为 GPL-v3.0-or-later。本项目保留原 Manifest 和作者信息，并附上 [GPL 第 3 版全文](licenses/GPL-3.0.txt)。

本项目新增的补丁和模块以 **GPL-3.0-or-later** 提供，不改变上游文件的作者和权利归属。
