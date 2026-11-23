# 生活状态接口

MaiWeave 决定当前生活状态下能否聊天、能否主动交流。MaiTogether 在受管目标发送前调用公开接口 `ilworkcn.maiweave.evaluate_behavior@1`。普通安装使用默认配置即可。作息设置见 [MaiWeave](plugins/maiweave.md)。

## 发送前如何查询

| 本次发送 | 传给 MaiWeave 的 `behavior` |
| --- | --- |
| 普通聊天回复，经 Host 的消息发送流程发出 | `conversation` |
| 插件发送的消息、戳一戳、贴表情、空间发布等 | `proactive` |

`life.py` 根据 Host 记录的调用来源、动作和消息编号选择参数。每次检查只查询一次。MaiWeave 返回 `allow / available` 后继续检查该目标的其他限制。返回 `defer`、`unknown` 或 `abstain` 时停止本次发送，日志保留 MaiWeave 给的原因。会话内的晚安告别由 MaiWeave 自身的发言钩子处理。

Host 验证接口注册、版本、行为类型及查询时间。单次查询限时 150 毫秒，`queried_at` 最多早于当前时间 180 秒。结果不缓存。接口缺失、超时、返回无效或调用期间被替换时停止发送。群静音由 MaiHush 决定，管理权限由 MaiIdentity 核对。

手动指定 MaiWeave 接口时使用 `api: evaluate_behavior` 和 `protocol: maiweave_behavior_v1`。只需调整结果的最长有效时间时，在 `life_provider` 中填写 `max_age_seconds` 即可。

## 其他后端

维护者可配置 `decision_v1`，但必须由新后端实现私有、静态、版本为 `1` 的状态 API，再完成组合验证。不能只替换插件 ID 就认为兼容。

业务参数为空；Host 通过内部调用信息传递真实会话、动作和来源。接口应只读状态，不发消息、不调用模型、不反向查询连接器。返回例子：

```json
{"version": 1, "decision": "allow", "reason": "available"}
```

`allow` 只接受 `available`；拒绝使用 `deny` 和具体原因。`abstain / not_managed` 只表示成功查询后确认该目标不归后端管理，不能表示故障。附带的 `ready` 与决定必须一致。

最终发送检查的总时限为 300 毫秒。

Host 后端由配置指定，插件不能自行替换默认后端。生活状态不授予管理员权限，也不表示活动内容适合公开分享。
