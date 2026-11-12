# SnowLuma QQ 连接器

[上游项目](https://github.com/Mai-with-u/MaiBot-SnowLuma-Adapter)

## 简介

连接 MaiBot 与 SnowLuma。MaiTogether 使用带发送检查的版本，在消息、戳一戳和贴表情等动作提交前查询生活和静音状态。

## 补充说明

[安装命令](../setup.md)会准备好 `adapter/`，无需自己给连接器打补丁。已有连接器时保留原 `config.toml`、地址、端口和数据，只替换代码；同一 Bot 实例只安装一份。

连接器与 Host 修改一起更新。不要用插件市场的原版直接覆盖配套版本，否则统一检查可能无法工作。机器人账号、群范围和 scope 仍需符合连接器自己的设置。

当前配套基于连接器 1.1.13。上游 1.3.1 要求 Host 至少 1.4.4，不能直接替换当前 Host 1.4.2 组合。

本项目不修改 SnowLuma 客户端，也不代替它的登录流程。
