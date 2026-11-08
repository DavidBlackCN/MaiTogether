# Cateye 表情回应

[项目与安装说明](https://github.com/cateyemizuki/cateye_set_msg_emoji_like_api_modify)

## 简介
给 QQ 消息贴表情，并接收表情回应通知。是否自动贴表情、使用哪些表情和冷却时间，在插件自己的配置页设置。

## 补充说明
- MaiTogether 示例已包含 `github.cateye.set-msg-emoji-like` 的自动行动权限。模型在当前聊天中调用表情工具和插件自动回应，都要经过配套连接器的发送检查。
- 参考版本读取机器人账号的方式可能使“贴表情成功”的记录未显示在聊天流中。判断是否成功先看 QQ 消息上的实际回应，不要因为聊天记录缺失就重复操作。
