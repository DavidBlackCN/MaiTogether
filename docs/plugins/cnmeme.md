# 麦麦黑话

[项目与安装说明](https://github.com/YukiSakiko/cnmeme_plugin)

## 简介

为麦麦提供网络梗、黑话、缩写和谐音词的内部查词工具，帮助理解聊天语境，不由插件向用户发送词义说明。

查词不依赖其他插件，也无需登录或填写密钥。可选将查到的明确释义收录进麦麦自己的黑话库。

## 推荐配置

为避免外部百科的错误释义污染已有的黑话库，建议默认关闭自动收录全局黑话。等实际使用一段时间，确认释义准确性后，再考虑启用自动收录。

```toml
[plugin]
enabled = true
public_api_enabled = false
config_version = "0.1.0"

[lookup]
timeout_seconds = 20
max_results = 3
max_content_length = 3000
cache_ttl_seconds = 60
save_global_jargon = false
save_global_expression = false
```