# Cateye 消息后处理

[项目与安装说明](https://github.com/cateyemizuki/cateye_better_post-processing)

## 简介

提供引用、分段、错字处理和表情包等功能，各项可分别开关。

**MaiBot 1.4.x 使用 [`host-1.4.0` 分支](https://github.com/cateyemizuki/cateye_better_post-processing/tree/host-1.4.0)**。该分支当前为 1.4.5；`main` 继续维护 1.3.x 兼容版本。

## 推荐配置

与[智能分段](smart-segmentation.md)同时使用，消息拆分交给智能分段，Cateye 保留引用、文字处理和表情包等所需功能。Cateye 配置：

```toml
[response_splitter]
enable = "关闭"
yield_to_other_plugins = true
final_newline_action = "保持原样"

[empty_reply_fallback]
enabled = false

[cross_chat_recall]
enabled = false
```

智能分段认领本轮正文后，Cateye 不再接管该正文的分段和错字处理；引用、文字规则和表情包等独立功能仍可使用。宿主开关按该分支 README 设置。

## 补充说明

- 示例配置已允许回复后表情包和跟风消息；这些发送仍受睡眠和静音限制。
- “跨聊私聊回忆”会把私聊信息用于群聊，建议保持关闭。空回复补发也先保持关闭，避免与回复守卫或神经闭环反馈相互抵消。
