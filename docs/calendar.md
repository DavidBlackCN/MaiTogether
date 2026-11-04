# 日期与生活设置

推荐原版 [日期上下文插件](https://github.com/xiexiaojia780/date_context_plugin)。本组合固定 1.4.6，提交 `72098e2919b7df9cc31d4431c87a09f63db8aba7`，安装方式和依赖见原仓库。

在该插件配置中设置：

```toml
[date]
timezone = "Asia/Shanghai"

[reply_injection]
enabled = true

[planner_injection]
enabled = true
```

同时将 Vita 的 `instance.timezone` 和宿主进程时区设为 `Asia/Shanghai`。宿主提供聊天中的日期时间，日期插件补充星期、节日等信息；Vita 每日计划和活动决策使用同一份日期材料。跨日或改变角色时区后重新查询，读取生活页面不会调用日期服务或模型。

日期插件缺失或暂时不可用时，Vita 仍使用当地公历日期和星期；节假日信息显示未知。原版 1.4.6 在部分年份缺少法定日历时仍返回两个 false，因此 Vita 不据此断言当天必须上班。真实节日安排还应以用户所在地的公告为准。

不同时启用同作者的 holiday_aware_planning_plugin，避免与 Vita 生成第二套日程。

## 聊天频率

只由 Vita 写入宿主的群聊生活倍率。Hush 负责静音，Coordinate 调整主动表达间隔；这两个插件都不再叠乘发言倍率。

Vita 默认平常 ×1，疲倦 ×0.6，专注 ×0.3，可用 `availability.adjust_group_frequency = false` 关闭。基础发言设置、分群和时段设置仍由 MaiBot 管理。倍率不会使群聊消息数严格按比例变化，也不作用于私聊。

不要同时启用另一个调频插件。官方接口只有一个共享数值，没有独占写锁；Vita 能发现已观测到的外部改值并停止覆盖，但无法保证并发写入不冲突。出现冲突时先关闭其他调频功能，再重载 Vita。
