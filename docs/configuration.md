# 更多配置

普通 QQ 群按[安装说明](setup.md)填写账号和群号即可。本页用于私聊、多账号及额外权限设置。

所有字段都在 Bot 实例的 `config/behavior_control.json` 中，修改后重启对应 Bot。

## 管理哪些会话

每个 `targets` 项代表一个群或一个私聊对象：

| 字段 | 填法 |
| --- | --- |
| `platform` | QQ 使用 `"qq"` |
| `account_id` | 机器人 QQ 号，字符串 |
| `scope` | 未设置连接器 scope 时用 `null`；设置过则与连接器一致 |
| `chat_type` | 群聊用 `"group"`，私聊用 `"private"` |
| `target_id` | 群号或私聊对象 QQ 号，字符串 |
| `providers` | 群聊用 `["life", "hush"]`；私聊用 `["life"]` |

`life` 检查 MaiWeave 生活状态，`hush` 检查群静音。名单外的会话不做这两项检查；开启统一控制后，未知 QQ 动作、敏感读取及未授权群管理操作仍会拒绝。

同群有多个机器人时，每个账号分别设置；不要把一个 Bot 的配置文件复制给所有实例。Hush 中的 `bot_account_id`、`route_scope` 也应对应。

## 哪些插件可以自动行动

`autonomous_plugins` 是允许在这个会话后台发送的插件 ID。ID 在插件的 `_manifest.json` 中，与目录名无关。

- 示例已包含[插件清单](plugins.md)中需要后台发送的插件，回复守卫除外。按清单安装时无需逐个添加。
- 只改提示词、查询资料或处理现有消息的插件，不需要后台发送权限。
- 安装清单外的插件时，只有其后台发送功能需要添加实际发送者的插件 ID。

加入名单不会打开插件自己的主动功能，也不会免除睡眠和静音检查。

`cross_target_plugins` 允许插件从一个会话向另一个受管理会话发起动作，默认 `[]`。只在确实需要跨群功能时设置。

## 管理权限

`management_commands` 默认 `[]`，不允许通过这套控制执行 QQ 踢人、禁言等管理动作。MaiIdentity 的管理员名单用于已接入的插件管理命令，不会自动获得任意 QQ 管理能力。

开发者接入群管理命令时，还需明确插件 ID、命令组件和允许的动作，并核对消息发送者与目标会话。不要把普通自动任务当成管理员调用。

## 生活状态和配置位置

生活后端默认是 MaiWeave，无需填写 API 名称或协议版本。`life_provider.max_age_seconds` 默认 180 秒，使用较慢生活更新间隔时需相应调整。详细规则见 [MaiWeave](plugins/maiweave.md)，接口开发见 [Life Provider](life-provider.md)。

`enabled` 控制这套发送检查是否启用。也可用 `MAIBOT_BEHAVIOR_CONFIG` 环境变量指定配置文件；多实例一般使用各自的默认路径，以免共享同一份配置。
