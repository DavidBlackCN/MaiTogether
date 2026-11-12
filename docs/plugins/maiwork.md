# MaiWork

[上游项目](https://github.com/CharTyr/MaiWork) · [配套适配与构建](../../integrations/maiwork/README.md)

## 简介

承担多 Agent 任务、Skill、MCP、工作台和文件交付。无需再开发一套 DSH 连接插件来重复这些能力。

配套适配基于 MaiWork 0.17.0，适配版本 1.2.1，配合 Host 1.4.3／SDK 2.22.1 使用。版本与构建方法见上方链接。

## 推荐配置

使用适配包并参考[推荐配置](../../integrations/maiwork/recommended.toml)：生活后端默认 MaiWeave，先关闭公开网页发布。服务群、模型和执行环境在 MaiWork 内设置；MCP 只开放需要的工具。

## 补充说明

- 示例配置已允许后台通知和交付。生活状态决定是否开始新工作，已获批任务可以收尾；群静音限制通知和交付，不取消正在计算的任务。结果未知时先核对 QQ，不自动重发。
- QQ 消息审批接入 Identity，工作台仍使用 MaiWork 自己的登录权限。SSH、MCP 和公开分享不属于 QQ 发送检查，执行环境的权限需要单独设置。
