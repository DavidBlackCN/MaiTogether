# MaiHush

让麦麦在指定群安静一段时间，再恢复发言。[上游安装说明](https://github.com/DavidBlackCN/maibot-maihush-plugin)

管理员来源使用 `identity`，在 [MaiIdentity](maiidentity.md) 填管理员账号。Hush 默认管理所有 QQ 群。只想管理部分群时，把 `scope.mode` 设为 `allowlist`，在 `scope.group_ids` 填群号。`excluded_groups` 中的群始终排除。

管理员发送 `/maihush mute 20m` 开始静音，`/maihush unmute` 提前结束。任何人都可以用 `/maihush status` 查看状态。首次静音的确认文案在 `reply.mute_text` 修改，关闭 `reply.enabled` 可省去确认回复。

希望麦麦也能听懂自然语言劝静时，开启 `social.enabled` 并填写已有的模型任务。要让其他插件的戳一戳、贴表情也受静音限制，该群还需在 [MaiTogether 管理范围](../configuration.md)内。
