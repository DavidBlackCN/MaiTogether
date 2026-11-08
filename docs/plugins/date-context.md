# 日期上下文

[项目与安装说明](https://github.com/xiexiaojia780/date_context_plugin)

## 简介

为聊天补充当前日期、星期、节日和调休参考。

## 推荐配置
由于 MaiWeave 自己已经会向 Planner 和 Replyer 注入生活上下文，如果再开启日期注入，就会增加重复上下文，建议保持插件默认的关闭规划与回复注入：

```toml
[date]
timezone = "Asia/Shanghai"

[reply_injection]
enabled = false

[planner_injection]
enabled = false
```

## 补充说明

- 需让日期插件、MaiWeave 的 `life.timezone` 和宿主进程使用同一个时区（默认Asia/Shanghai）。
- 参考版本在部分年份缺少法定日历时，结果不能作为“当天必须上班”的依据。日程由 MaiWeave 管理，这个插件提供时间参考，不需要后台发送权限。
