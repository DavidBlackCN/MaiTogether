# 常见问题

## 睡着后还能收到消息、调用模型吗？

可以。消息接收、聊天思考、唤醒和记忆按 MaiBot、MaiWeave 的原生方式运行。MaiTogether 在对外发送前询问 MaiWeave 是否允许本次回复或互动，并检查群静音。午睡时能否回话取决于 MaiWeave 的午睡静默设置。

想节省睡眠期间的模型调用，可分别设置普通群聊和普通私聊跳过 Planner，两个开关默认关闭。位置和对聊天历史的影响见 [MaiWeave 的睡眠设置](plugins/maiweave.md#睡眠和发言)。

## 装了插件却没回应

先看 MaiWeave 当前是否睡眠或忙碌，再查看 `/maihush status`。如果状态正常，搜索 Host 日志中的 `behavior_control`：

| 原因 | 先检查什么 |
| --- | --- |
| `life:sleeping`、`life:busy` | MaiWeave 当前生活状态 |
| `life:not_ready`、`life:disabled` | MaiWeave 的生活功能是否已启用、加载完成 |
| `LIFE_PROVIDER_PROTOCOL` | MaiWeave 的行为接口版本、返回的行为类型和查询时间是否有效 |
| `life_state_stale` | 查询时间是否过期，宿主与插件的系统时间是否一致 |
| `LIFE_PROVIDER_MISSING`、超时 | MaiWeave 是否加载成功；其他必要插件是否正常 |
| `BEHAVIOR_BACKGROUND_TARGET_DENIED` | 运行配置中对应会话的名单是否与示例一致；清单外插件见[自动行动权限](configuration.md#哪些插件可以自动行动) |
| `BEHAVIOR_ADAPTER_CONTRACT_UNAVAILABLE` | 是否使用配套连接器，以及账号、scope 是否一致 |
| `BEHAVIOR_ACTION_UNCLASSIFIED` | 动作尚未支持；反馈动作名，不要直接关闭检查 |

MaiHush 和 QQ 连接器自己的群范围也会限制发送。群号、机器人账号填错，可能使预期的保护没有作用，或让正常操作被拒绝。

## 安装时提示版本不符或源码有修改

安装器只处理[当前版本清单](../baseline.json)对应的官方源码，防止覆盖你的改动。这项限制针对 Host 和配套连接器，不要求生态中的所有社区插件锁在同一批版本。

同版本安装可以重复执行。若提示未知修改，先查看报出的路径，保留自己的改动，再使用匹配的官方版本。升级或中断后的恢复见[更新与恢复](setup.md#更新与恢复)。

## 为什么只发出了一部分？

文件、转发和多条消息逐项检查，途中睡眠或静音会停止后续发送。超时也可能只是没有收到回执。先查看 QQ 实际结果，不要整批重发。

## 加新插件要重新构建吗？

通常不需要。照插件自己的说明安装即可，示例已包含插件清单所需的后台发送权限，回复守卫除外。清单外插件的后台发送见[自动行动权限](configuration.md#哪些插件可以自动行动)。通过配套连接器发布空间动态会检查生活状态。插件自行联网或调用外部工具时，按插件自己的设置管理。
