# 日期与时区

[日期上下文插件](https://github.com/xiexiaojia780/date_context_plugin)可为聊天补充星期、节日和调休信息。配置参考版本为 1.4.6，提交 `72098e2919b7df9cc31d4431c87a09f63db8aba7`；安装方式和依赖见原仓库。

在该插件配置中设置：

```toml
[date]
timezone = "Asia/Shanghai"

[reply_injection]
enabled = true

[planner_injection]
enabled = true
```

将 MaiWeave 的 `life.timezone`、日期插件和宿主进程时区设为同一个时区，例如 `Asia/Shanghai`。MaiWeave 按自身时区安排生活，日期插件补充聊天上下文；开启聊天注入不代表 MaiWeave 的后台自主规划会调用该插件。

版本 1.4.6 在部分年份缺少法定日历时仍可能返回两个 false，不能据此断言当天必须上班。具体节日安排以所在地公告为准。

日程由 MaiWeave 统一管理，日期插件只提供时间参考。

## 聊天频率

基础发言频率由 MaiBot 管理，主动交流的对象、间隔和每日额度在 MaiWeave 中设置。MaiTogether 根据生活状态决定是否暂停认知或动作，Hush 负责群静音；具体规则见 [MaiWeave 配置](maiweave.md)。
