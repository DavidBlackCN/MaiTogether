# MaiHush

[项目与安装说明](https://github.com/DavidBlackCN/maibot-maihush-plugin)

## 简介

管理指定群的安静时段。管理员可以发送 `/maihush mute 20m`、`/maihush unmute`，普通状态查询用 `/maihush status`。

## 推荐配置

```toml
# 示例配置基于 config.example.toml
# 完整配置说明请查阅源项目仓库
default_minutes = 20
autonomous_enabled = false

[plugin]
enabled = true
config_version = "2"

# 管理模式相关
[scope]
mode = "all"
group_ids = []
excluded_groups = []

# 管理渠道相关
[management]
source = "identity"
admin_accounts = []

# 自然劝静
[social]
enabled = true
task_name = "planner"
max_seconds = 300

# 命令静音回应
[reply]
enabled = true
mute_text = "好，我先安静 {duration}。"
```

## 补充说明

- 管理员名单在 MaiIdentity 中维护。自然语言劝静是可选功能，在 Hush 的 `social` 配置中开启并选择已有模型任务。
- 首次命令静音默认回应一句，文案在 `reply.mute_text` 中修改；不需要确认回复时关闭 `reply.enabled`。确认只用于这次静音，不给其他发送提供豁免。
- MaiTogether 的配置示例已包含 Hush 的自动行动权限。让 `targets` 中的群与 Hush 的受管理群一致，其他插件经配套连接器发送的消息、戳一戳和表情回应也会受限。
