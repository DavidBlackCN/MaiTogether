# Cateye 消息后处理

[项目与安装说明](https://github.com/cateyemizuki/cateye_better_post-processing)

## 简介

提供引用、分段、错字处理和表情包等功能，各项可分别开关。

**MaiBot 1.4.x 使用 [`host-1.4.0` 分支](https://github.com/cateyemizuki/cateye_better_post-processing/tree/host-1.4.0)**。该分支当前为 1.4.5；`main` 继续维护 1.3.x 兼容版本。

## 推荐配置

建议只开启需要的处理。使用[智能分段](smart-segmentation.md)时不要再开第二套分段；由本插件接管错字或后处理时，按该分支 README 设置宿主开关。

## 补充说明

- 示例配置已允许补发分段、回复后表情包和跟风消息；这些发送仍受睡眠和静音限制。
- “跨聊私聊回忆”会把私聊信息用于群聊，建议保持关闭。空回复补发也先保持关闭，避免与回复守卫或神经闭环反馈相互抵消。
