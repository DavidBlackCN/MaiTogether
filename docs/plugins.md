# 插件清单

按需要选择插件，不必全部安装。安装方法与详细配置请参考各插件仓库。

## 核心插件

| 插件 | 用途 | 本组合使用的版本 |
| --- | --- | --- |
| [MaiHush](https://github.com/DavidBlackCN/maibot-maihush-plugin) | 群静音、恢复发言和发送次数限制 | 0.3.1 |
| [MaiIdentity](https://github.com/DavidBlackCN/maibot-maiidentity-plugin) | 固定身份提示、管理员名单和命令权限 | 3.4.1 |
| [MaiWeave](https://github.com/ilworkcn/MaiWeave) | 日程、活动、睡眠、生活经历与主动交流 | [源码基线](../integrations/maiweave/baseline.json)；[配置说明](maiweave.md) |
| [搜索中枢](https://github.com/kamionichan/maibot-search-hub) | 搜索 | — |

要让其他插件的 QQ 动作也遵守生活状态和静音限制，还需要本项目修改后的 MaiBot 主程序和 QQ 连接器。

## 回复优化

| 插件 | 用途 |
| --- | --- |
| [回复守卫](https://github.com/42yoru/maimai-reply-guard)（评估中） | 回复检查 |
| [智能分段](https://github.com/saberlights/smart_segmentation_plugin) | 回复分段 |
| [Cateye 消息后处理](https://github.com/cateyemizuki/cateye_better_post-processing) | 消息后处理 |
| [Smart Poke](https://github.com/TAIY2020/smart_poke_plugin) | 智能戳一戳 |
| [Cateye 表情回应](https://github.com/cateyemizuki/cateye_set_msg_emoji_like_api_modify) | 给 QQ 消息贴表情，接收表情通知 |
| [maibot-corpus-callosum](https://github.com/yufei-pan/maibot-corpus-callosum) | 神经闭环反馈 |

## 其他插件

| 插件 | 用途 |
| --- | --- |
| [Self-Identity](https://github.com/ValleyWinds/Self-Identity) | 自我信息 |
| [MaiBot Tarots](https://github.com/A0000Xz/MaiBot-Tarots-Plugin) | 塔罗牌 |
| [MaiWork](https://github.com/CharTyr/MaiWork) | Agent 工作系统、多任务、Skill、MCP 与文件交付；使用[配套适配](../integrations/maiwork/README.md) |
| [日期上下文](https://github.com/xiexiaojia780/date_context_plugin) | 聊天中的日期、节日与调休参考；[配置说明](calendar.md) |

## 搭配说明

Smart Poke 和 Cateye 表情回应的后台自动回应需要列入[允许自动行动的插件名单](setup.md#允许自动行动的插件)。

**Cateye 已知问题**：当前表情回应插件读取机器人账号的字段与 Host 返回格式不一致，可能导致“贴表情成功”的记录未显示在聊天流中。

新增插件时，先确认它通过什么方式发送消息或执行动作。使用官方 QQ 连接器的插件可以共用发送检查；自行调用外部服务的插件需要另行评估。
