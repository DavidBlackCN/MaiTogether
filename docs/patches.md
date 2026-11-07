# 补丁边界

默认组合修改 20 个 Host 官方文件和 5 个 QQ 连接器官方文件，不修改 SDK。独立逻辑放在新增模块，官方文件只保留接入调用和必要的返回值处理。

## Host 接入位置

以下路径均相对于官方 Host 的 `src/`。共用基础 7 个文件，行为控制 4 个，睡眠暂停 9 个。只构建行为控制涉及 11 个 Host 文件；只构建睡眠暂停涉及 16 个。

| 组 | 官方文件 | 保留原因 |
| --- | --- | --- |
| 共用 | `plugin_runtime/capabilities/registry.py` | 注册策略查询能力 |
| 共用 | `plugin_runtime/host/capability_service.py` | 接收并校验真实调用上下文 |
| 共用 | `plugin_runtime/host/rpc_server.py` | Host 向 Runner 传递内部上下文 |
| 共用 | `plugin_runtime/host/supervisor.py` | 分配和结束调用生命周期 |
| 共用 | `plugin_runtime/protocol/envelope.py` | 内部协议字段独立于插件业务参数 |
| 共用 | `plugin_runtime/runner/rpc_client.py` | 进入、退出 Runner 调用作用域 |
| 共用 | `plugin_runtime/runner/runner_main.py` | 回传调用引用，向核心插件提供只读控制状态 |
| 行为 | `platform_io/manager.py` | 标准消息发送检查与结果记录 |
| 行为 | `plugin_runtime/capabilities/core.py` | 让调用方区分未提交、部分完成和结果未知 |
| 行为 | `plugin_runtime/component_query.py` | 在 Tool、Command 的真实入口记录来源；旧 Action 兼容调用沿用官方 Tool 路径 |
| 行为 | `plugin_runtime/host/hook_dispatcher.py` | Hook 熔断不能当作执行成功 |
| 睡眠 | `chat/heart_flow/heartflow_message_processor.py` | 睡眠消息只入原始记录，不唤醒聊天 |
| 睡眠 | `maisaka/runtime.py` | 其他消息入口也不能绕过暂停 |
| 睡眠 | `maisaka/reasoning_engine.py` | 清理已排队触发，停止循环和压缩，过滤仅记录消息 |
| 睡眠 | `maisaka/chat_loop_service.py` | 在实际 Planner 请求前复查，覆盖共享 Planner |
| 睡眠 | `maisaka/focus/group_runtime.py` | 共享会话暂停及队列处理 |
| 睡眠 | `chat/replyer/maisaka_generator_base.py` | Replyer 请求、重试和续写前复查 |
| 睡眠 | `maisaka/builtin_tool/reply.py` | 统一清理未发送草稿，避免进入后续上下文 |
| 睡眠 | `services/memory_flow_service.py` | 自动记忆入口、任务消费和历史筛选 |
| 睡眠 | `A_memorix/core/utils/summary_importer.py` | 自动总结排除睡眠记录 |

这些入口处于不同阶段，不能仅靠收消息时检查一次。收到消息后才入睡、生成后发送失败、重启后读取历史记录，都需要后续阶段处理。

## 连接器接入位置

| 官方文件 | 保留原因 |
| --- | --- |
| `_manifest.json` | 声明调用 Host 策略的能力 |
| `plugin.py` | 创建检查服务 |
| `runtime_state.py` | 保存检查服务引用 |
| `services/action_service.py` | 批量动作预检查和逐项结果 |
| `transport.py` | 等待发送队列后、写 WebSocket 前终检 |

批量预检查只确认动作类型、目标和来源，不生成票据，也不扣静音额度。每个实际子动作另行准备并终检，不能用批量放行代替逐项判断。

## 模块职责

新增源码位于 `host/src/plugin_runtime/behavior_policy/`：`context.py` 管调用生命周期，`runtime.py` 管策略和结果，`actions.py` 管动作分类；`platform.py` 处理标准发送；`sleep_guard.py` 判断睡眠和过滤记录，`cognition_hooks.py` 适配官方聊天、回复和记忆入口。`build_features.py` 由构建选择功能。

两个功能共用可信调用和策略访问，不各自实现一套身份系统。代码使用显式调用或装饰器，不在启动时替换官方方法。1.4.1 的回复缓存、提示词构建后的请求和创意模式翻译均在启动前复查生活状态；Focus 队列使用官方的新接口清理暂停输入。升级时重点复核本表中的入口及相应新增模块。

## 保留的限制

- 仅覆盖标准消息出口和官方 QQ 连接器；独立 HTTP／WebSocket、QQ 空间、任意外部写工具不在范围内。
- 这是正常插件之间的执行约束，不是恶意 Python 插件的安全隔离。
- 状态检查与远端 QQ 执行不构成跨进程事务。终检后立即提交，已提交请求允许收尾；未知结果不自动重发。
- 已开始的模型请求以及社区插件独立调用的模型不能保证取消，睡眠不等于所有模型费用为零。
- 自动应用成功不保证新版语义兼容，仍需检查官方接口差异并运行回归。
