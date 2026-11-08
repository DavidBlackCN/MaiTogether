# 补丁范围

MaiTogether 修改 **8 个 Host 官方文件、5 个 QQ 连接器官方文件**，不修改 SDK。新增逻辑集中在本项目模块，官方聊天、回复生成和记忆代码保持原样。

## Host

以下路径相对于官方 `src/`：

| 文件 | 作用 |
| --- | --- |
| `plugin_runtime/capabilities/registry.py` | 注册发送检查及发送结果接口 |
| `plugin_runtime/host/capability_service.py` | 校验调用来源，附带发送结果 |
| `plugin_runtime/host/supervisor.py` | 记录一次真实调用的起止 |
| `plugin_runtime/runner/rpc_client.py` | 在 Runner 中接收调用信息 |
| `plugin_runtime/runner/runner_main.py` | 回传 Host 分配的调用引用 |
| `plugin_runtime/component_query.py` | 从命令和工具入口记录发送者、目标会话 |
| `platform_io/manager.py` | 检查标准消息发送 |
| `plugin_runtime/host/hook_dispatcher.py` | Hook 熔断时报告失败，不能当作检查成功 |

Host 判断谁发起动作、发往哪里。插件参数中的 `is_owner` 等字段不作为授权依据，后台任务也不能长期继承一次管理员命令的权限。

## QQ 连接器

| 文件 | 作用 |
| --- | --- |
| `_manifest.json` | 声明检查所需能力 |
| `plugin.py` | 创建检查服务 |
| `runtime_state.py` | 保存检查服务 |
| `services/action_service.py` | 预检查批量操作并记录逐项结果 |
| `transport.py` | 排队结束、实际写入 WebSocket 前检查 |

批量预检查不生成发送票据，也不扣静音额度。每个实际子动作单独检查，因此生成中入睡、排队期间静音也能阻止尚未提交的动作。已提交请求允许收尾，未知结果不自动重发。

## 新增模块

`host/src/plugin_runtime/behavior_policy/` 中，`context.py` 记录调用来源，`actions.py` 分类 QQ 动作，`runtime.py` 汇总生活、静音和权限判断，`platform.py` 与 `delivery.py` 处理发送及结果，`life.py` 与 `life_status.py` 读取和解释生活状态。

睡眠、忙碌来自 MaiWeave，群静音来自 Hush，管理授权来自 Identity。必要接口缺失、异常或超时会拒绝对应动作。

## 限制

- 不控制插件独立 HTTP／WebSocket、QQ 空间和任意外部写工具。
- 不隔离恶意 Python 插件，也不代替操作系统权限。
- 不暂停聊天模型或改写记忆。相关行为交给官方和生活插件。
- 状态检查与 QQ 执行不是一个事务，检查后已经提交的请求可能在状态改变后才显示。
- 新版补丁能自动应用，不代表接口含义没变，升级仍需回归。
