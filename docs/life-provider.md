# Life Provider 维护说明

MaiTogether 通过 Life Provider 查询生活条件，决定是否暂停对话认知或阻止外部动作。用户配置见 [MaiWeave 接入](maiweave.md)，本文说明接口、模块和兼容规则。

## 后端选择

目标使用 `providers: ["life", "hush"]`，行为配置顶层明确选择后端：

```json
"life_provider": {
  "plugin_id": "ilworkcn.maiweave",
  "api": "get_life_status",
  "version": "1",
  "protocol": "maiweave_status_v1",
  "max_age_seconds": 180
}
```

由管理员在 Host 配置中选择唯一后端，不允许插件自行注册为默认后端。新后端需要核对 API 和状态语义，不能只替换插件 ID。

指定后端不可用时拒绝相关动作，不自动寻找替代插件。只有 Hush 的目标仅受群静音保护。更改行为配置后重启 Host。

## 模块与调用

- `behavior_policy/life.py`：配置、名称转换、API 解析、超时及结果校验。
- `life_status.py`：将 MaiWeave 的只读状态转换为生活条件；同一份代码随 MaiWork 适配构建，避免两处规则不同。
- `runtime.py`：组合 Life、Hush 与 Identity 的决策，维护动作票据和最终发送检查，不解释生活引擎内部状态。
- `sleep_guard.py`：向同一个 Life Provider 发出认知查询，保留睡眠消息标记、历史和自动记忆处理。

生活接口适用于两类查询：`cognition` 检查对话认知，`social` 检查外部社交。忙碌是否影响认知由对应协议决定。群静音和管理员权限仍由 Hush、Identity 提供。

Host 从正式 API 注册表选择指定插件、名称、版本的唯一且已启用组件，再按其处理函数调用。默认 `decision_v1` 协议要求私有 API；只有显式配置 `maiweave_status_v1` 时，才接受固定的 `ilworkcn.maiweave.get_life_status` 公开 API。不能将任意公开 API 当作权限 Provider。接口卸载、可见性变化、停用、版本不符或调用期间被替换，均不能使用其结果。当前只支持版本 `1` 的静态 API。

业务参数为空。请求由 Host 放入可信调用上下文，包含真实路由、会话、动作类别与来源；`is_owner`、`verified` 等普通参数不能充当权限。后端应只读状态、不调用模型、不发送消息、不反向查询连接器，也不能把整个生活提示词作为结果返回。

## v1 返回约定

SDK 信封内的结果对象示例：

```json
{"version": 1, "decision": "allow", "reason": "available", "revision": 123}
```

| 返回 | 含义 |
| --- | --- |
| `allow / available` | 生活条件允许继续；仍需其他策略和原有权限通过 |
| `deny / sleeping`、`busy`、`not_ready`、`state_unknown` 等原因 | 拒绝本次认知或动作 |
| `abstain / not_managed` | 后端明确排除了这个会话；其他策略仍执行 |

`version` 必须是整数 1，`decision` 和非空 `reason` 必须有效。未知状态不能以 `allow` 返回；`allow` 的原因仅接受 `available`。若附带 `ready`，允许或明确排除范围的结果要求它为 `true`，不能同时声称未就绪。`revision` 用于诊断，不缓存发送许可。

`not_managed` 是成功查询得到的明确范围排除，不等于插件缺失或读取失败；不能用它表示故障。正式需要保护的会话应同时纳入 Host 和生活插件的管理范围。

单次 RPC 预算仍为 150ms，原有终检总预算仍为 300ms。异常、超时、无效信封和协议不符会拒绝；睡眠查询将异常显示为 `life_state_unavailable`。生活拒绝日志使用 `life:原因`，例如 `life:busy`。不会为预检查新增额度消耗，也不修改 Hush 的一次性回执或管理员边界。

## 适配其他生活插件

配置能力不代表任意插件已兼容。新后端需要正式确定接口，验证状态语义、生命周期、读取成本、异常处理及真实组合。MaiWeave 使用上游已实现的公开状态 API；受管范围与动作类别由 Host 决定，不把活动内容解释成授权，也不读取插件数据库。睡眠字段仍有[已反馈的缺口](https://github.com/ilworkcn/MaiWeave/issues/2)，详见[接入说明](maiweave.md)。

公开生活素材和主动表达不属于这个安全查询接口。MaiWork 的查询只决定是否启动工作，不授予发送或管理权限。Host 和 MaiWork 的后端必须分别配置且保持一致，详见其[维护说明](../integrations/maiwork/README.md)。

## 兼容与回滚

为保留已有组合的回滚能力，代码在省略 `life_provider` 时仍选择 MaiVita 的私有 `evaluate_behavior@1`。旧目标名 `vita` 会转为 `life`，不改写配置文件；不能与自定义后端或同一目标中的 `life` 混用。MaiWork 省略后端时也保持 Vita，因此使用 MaiWeave 时必须填写推荐配置中的显式后端。

回滚时恢复匹配的代码、配置和数据。若回到不识别 `life` 的旧版 MaiTogether，使用对应版本的配置。Provider 改造没有改变数据库格式，也不转换两个生活引擎的数据。
