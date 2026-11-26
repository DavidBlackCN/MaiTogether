# 补丁范围

MaiTogether 修改 **7 个 Host 官方文件、5 个 QQ 连接器官方文件**。调用来源、生活状态和权限判断由 MaiTogether 自己的模块处理。

## Host

以下路径相对于官方 `src/`：

| 文件 | 作用 |
| --- | --- |
| `plugin_runtime/capabilities/registry.py` | 注册发送检查及发送结果接口 |
| `plugin_runtime/host/capability_service.py` | 校验调用来源，附带发送结果 |
| `plugin_runtime/host/supervisor.py` | 记录一次真实调用的起止 |
| `plugin_runtime/runner/runner_main.py` | 注册请求时接入 Host 的调用信息，插件调用能力时回传本次引用 |
| `plugin_runtime/component_query.py` | 从命令和工具入口记录发送者、目标会话 |
| `platform_io/manager.py` | 检查标准消息发送 |
| `plugin_runtime/host/hook_dispatcher.py` | Hook 熔断时报告失败，不能当作检查成功 |

Host 判断谁发起动作、发往哪里。插件参数中的 `is_owner` 等字段不作为授权依据，后台任务也不能长期继承一次管理员命令的权限。

## QQ 连接器

| 文件 | 作用 |
| --- | --- |
| `_manifest.json` | 声明检查所需能力 |
| `plugin.py` | 创建检查服务，预检查批量操作并返回已完成的数量 |
| `runtime_state.py` | 向 Host 报告当前连接编号和支持的检查接口版本 |
| `services/action_service.py` | 收到 QQ 回应后，结合投递确认记录动作结果 |
| `transport.py` | 排队结束、实际写入 WebSocket 前检查 |

批量预检查不生成发送票据，也不扣静音额度。每个实际子动作单独检查，因此生成中入睡、排队期间静音也能阻止尚未提交的动作。已提交请求允许收尾，未知结果不自动重发。

## 新增模块

`host/src/plugin_runtime/behavior_policy/` 中，`context.py` 记录调用来源，`actions.py` 分类 QQ 动作，`runtime.py` 汇总生活、静音和权限判断，`platform.py` 与 `delivery.py` 处理发送及结果，`life.py` 向 MaiWeave 查询本次回复或主动互动能否发送。

睡眠、忙碌来自 MaiWeave，群静音来自 Hush，管理授权来自 Identity。必要接口缺失、异常或超时会拒绝对应动作。

## 限制

- 通过配套连接器发空间动态会检查生活状态。插件独立使用 HTTP、WebSocket 或外部工具执行的操作由插件自己管理。
- 不隔离恶意 Python 插件，也不代替操作系统权限。
- 不暂停聊天模型或改写记忆。相关行为交给官方和生活插件。
- 状态检查与 QQ 执行不是一个事务，检查后已经提交的请求可能在状态改变后才显示。
- 新版补丁能自动应用，不代表接口含义没变，升级仍需回归。
