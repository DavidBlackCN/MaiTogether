# 插件清单

按需要选择插件，不必全部安装。下面分别列出本项目的基础插件、可选功能和仍待评估的社区插件。

## 基础插件

| 插件 | 用途 | 本组合使用的版本 |
| --- | --- | --- |
| [MaiVita](https://github.com/DavidBlackCN/maibot-maivita-plugin) | 日程、活动、身体状态、睡眠与生活页面 | 0.10.0 |
| [MaiHush](https://github.com/DavidBlackCN/maibot-maihush-plugin) | 群静音、恢复发言和发送次数限制 | 0.3.1 |
| [MaiIdentity](https://github.com/DavidBlackCN/maibot-maiidentity-plugin) | 固定身份提示、管理员名单和命令权限 | 3.4.1 |

这三个插件可以独立使用。要让其他插件的 QQ 动作也遵守限制，还需要本项目修改后的 MaiBot 主程序和 QQ 连接器。

## 可选功能

| 插件 | 用途 | 当前说明 |
| --- | --- | --- |
| [MaiCoordinate](https://github.com/DavidBlackCN/maibot-maivita-plugin/tree/main/ecosystem/coordinator) | 根据生活状态安排主动分享和空间互动 | 0.5.0，随 Vita 仓库维护；不需要主动表达时可以不装 |
| [日期上下文](https://github.com/xiexiaojia780/date_context_plugin) | 日期、节日与调休参考 | 固定 1.4.6，原版使用；[配置及限制](calendar.md) |
| [MaiTrace 适配版](https://github.com/DavidBlackCN/maibot-maivita-plugin/tree/main/ecosystem/maitrace) | 为 Coordinate 提供 QQ 空间发布、浏览和互动 | 使用固定版本和配套补丁；空间功能由这两个插件自行检查状态，不属于本项目的 QQ 发送检查范围 |
| [Smart Poke](https://github.com/TAIY2020/smart_poke_plugin) | 收到戳一戳后作出回应 | 已用原版 1.11.1 测试正常回应及睡眠时的文字、回戳限制 |
| [Cateye 表情回应](https://github.com/cateyemizuki/cateye_set_msg_emoji_like_api_modify) | 给 QQ 消息贴表情，接收表情通知 | 已用原版 0.3.2 测试正常贴表情及睡眠、忙碌、静音时的限制；存在下述记录问题 |

Smart Poke 和 Cateye 的测试使用真实主程序和插件、本地模拟 QQ，没有连接真实账号。它们的后台自动回应需要列入[允许自动行动的插件名单](setup.md#允许自动行动的插件)。

**Cateye 已知问题**：在当前组合中，插件读取机器人账号的字段与 Host 返回格式不一致，可能导致“贴表情成功”的记录未显示在聊天流中。贴表情和发送限制已通过隔离测试，记录显示问题尚未修复。

## 待评估的选用清单

这些插件列入搭配方案，但尚未完成与本项目的兼容测试。这里不提供已经验证可用的版本或配置。

| 用途 | 插件 | 状态 |
| --- | --- | --- |
| 搜索 | [搜索中枢](https://github.com/kamionichan/maibot-search-hub) | 待验证组合兼容性 |
| 回复检查 | [回复守卫](https://github.com/42yoru/maimai-reply-guard) | 评估中 |
| 回复分段 | [智能分段](https://github.com/saberlights/smart_segmentation_plugin) | 待验证组合兼容性 |
| 消息后处理 | [Cateye 消息后处理](https://github.com/cateyemizuki/cateye_better_post-processing) | 待验证组合兼容性 |

新增插件时，先确认它通过什么方式发送消息或执行动作。使用官方 QQ 连接器的插件可以共用发送检查；自行调用外部服务的插件需要另行评估。
