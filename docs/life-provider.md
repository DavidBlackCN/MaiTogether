# 生活状态接口

本页供维护者接入生活插件。用户设置见 [MaiWeave](plugins/maiweave.md)。

MaiTogether 读取生活状态，只决定是否允许对外动作，不管理日程、不调用生活模型、不暂停聊天。默认后端是 `ilworkcn.maiweave.get_life_status@1`，普通配置可省略 `life_provider`。

## 模块

- `life.py`：选择已注册 API，检查版本、可见性、超时和返回值。
- `life_status.py`：解释 MaiWeave v1 状态；同一文件随 MaiWork 适配构建。
- `runtime.py`：结合生活、Hush 静音及 Identity 管理权限，在发送前决定是否继续。

Host 使用 `social` 查询；MaiWork 的共享解析器还支持 `work`，用于判断是否开始新任务。状态查询不是发送授权。

## MaiWeave v1

默认配置等价于：

```json
{
  "life_provider": {
    "plugin_id": "ilworkcn.maiweave",
    "api": "get_life_status",
    "version": "1",
    "protocol": "maiweave_status_v1",
    "max_age_seconds": 180
  }
}
```

仅接受正式注册、启用且版本相符的静态 API。`maiweave_status_v1` 只接受上述固定公开接口，不允许任意公开 API 提供授权。调用期间插件被卸载、替换或改变接口属性时，返回结果作废。

使用 MaiWeave 0.11.3 新增的 `effective_sleeping`、`sleep_until` 和 `queried_at`。每次发送检查重新查询，检查就绪状态、活动时段、临时唤醒与睡眠截止时间。缺少必要字段、结果过期或时间边界已变化时拒绝。

`queried_at` 用于结果有效期检查，`updated_at` 记录精力、心情与位置等保存状态的更新时间。实际睡眠由 `effective_sleeping` 决定，正常空闲可以放行。Host 的社交动作和 MaiWork 的新任务仍在工作、学习、出行时暂停。

MaiWeave 同时提供公开的 `evaluate_behavior(behavior="conversation" | "proactive")`。它的对话规则允许部分午睡回复，主动规则的活动范围也与本项目有所不同。当前接入继续读取 `get_life_status`，执行统一的实际睡眠与忙碌限制。具体行为见 [MaiWeave 页面](plugins/maiweave.md#状态判断)。

## 其他后端

维护者可配置 `decision_v1`，但必须由新后端实现私有、静态、版本为 `1` 的状态 API，再完成组合验证。不能只替换插件 ID 就认为兼容。

业务参数为空；Host 通过内部调用信息传递真实会话、动作和来源。接口应只读状态，不发消息、不调用模型、不反向查询连接器。返回例子：

```json
{"version": 1, "decision": "allow", "reason": "available"}
```

`allow` 只接受 `available`；拒绝使用 `deny` 和具体原因。`abstain / not_managed` 只表示成功查询后确认该目标不归后端管理，不能表示故障。附带的 `ready` 与决定必须一致。

单次生活查询预算 150ms，最终检查总预算 300ms。缺失、超时、异常或格式错误都会拒绝发送，不另找后端放行。日志保留 `life:原因`。

Host 后端由配置指定，插件不能自行替换默认后端。生活状态不授予管理员权限，也不表示活动内容适合公开分享。
