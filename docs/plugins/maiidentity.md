# MaiIdentity

[项目与安装说明](https://github.com/DavidBlackCN/maibot-maiidentity-plugin)

## 简介

配置熟悉的人、相处方式和管理员。固定身份影响称呼与提示词，管理员名单决定已接入命令的使用权限，两者分别设置。

## 推荐配置

```toml
# 示例配置基于 config.example.toml
# 完整配置说明请查阅源项目仓库
[plugin]
enabled = true
config_version = "4"

# 身份验证相关，建议在 webui 配置
[identity]
adapter_namespace = "host-qq"
route_scope = ""

[[identity.people]]
qq = "123456789"
nickname = "妈妈"
prompt_template = "与{nickname}自然亲近，可以撒娇，关心点到为止。"
style = ""
group_id = ""
enabled = false

[[identity.styles]]
name = "家人"
prompt = "与{nickname}自然亲近，关心点到为止，不必反复重复称呼。"

# 管理员相关配置，建议在 webui 配置
[management]
admin_accounts = []

[context]
enabled = true
budget_bytes = 2048
cache_ttl_seconds = 300
```

## 补充说明

- 在 WebUI 的插件配置页填写 `identity.people` 和 `management.admin_accounts`。身份工作区可以查看名单、模板和提示词预览；配置保存仍通过官方配置页完成。
- 与 MaiHush 搭配时，把 Hush 的管理员来源设为 `identity`。不要同时启用另一套给用户登记身份的提示插件。[Self-Identity](self-identity.md)描述的是麦麦自己，可以搭配使用。
- 无需为身份提示添加自动行动权限；它也不会因为有人使用“麦麦的妈妈”等群昵称就授予对应身份或管理员权限。
