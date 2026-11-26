# 智能分段

用模型将较长回复拆成几条连续消息。[上游安装说明](https://github.com/HaoxiangXia/smart_segmentation_plugin)

## 推荐配置

必须先禁用 `config/bot_config.toml` 中宿主自带的 `response_splitter`，否则会和本插件重复切分。

```toml
[response_splitter]
enable = false
```

建议先选 `natural` 风格和响应较快的小模型，再按实际观感调整段数。

## 与其他插件搭配

- 与 [Cateye 后处理](cateye-post-processing.md)同时使用，由本插件负责分段，关闭 Cateye 自带分段。
- 示例配置已允许后台发送后续分段。每段单独检查；中途睡眠或静音可能只发出前几段，不应把整段回复重新发送。
