# MaiWork 适配维护

用途、推荐设置和使用限制见 [MaiWork 插件页](../../docs/plugins/maiwork.md)。这里保存固定上游源码的补丁，不维护另一份完整 MaiWork。

| 项目 | 记录 |
| --- | --- |
| MaiWork | 0.17.0 |
| 适配版本 | 1.2.1 |
| 完整组合 Host / SDK | 1.4.3 / 2.22.1 |
| QQ 连接器 | 1.1.13 配套修改版 |

准确提交见 [baseline.json](baseline.json)。真实账号、执行环境和长期运行仍需在部署环境验收。

## 构建

```bash
git clone https://github.com/CharTyr/MaiWork.git ../MaiWork-upstream
python integrations/maiwork/build.py --source ../MaiWork-upstream --output ../MaiWork-adapted
```

构建从固定提交提取源码，应用 `maiwork.patch`、复制 `modules/` 和 Host 的 `life_status.py`，保留上游 ID、作者与许可证。输出目录必须不存在；`maitogether-build.json` 记录来源和哈希。

## 联动约定

- `together.enabled = true` 时启用生活、授权和发送联动；接口异常不改走原始发送路径。
- `together.life_provider = "maiweave"`，状态有效时间与 Host 保持一致，默认 180 秒。
- `together.public_publish = false` 禁止向 here.now 发布任务网页、附件回退和续期内容。`console.herenow_share` 不是这个开关的替代。
- 消息中的批准、拒绝接入 Identity 管理员查询；取消也保留任务发起人和群管理路径。任务只能在所属群处理。
- 睡眠或状态不可用时暂停新工作；已获批任务可收尾。通知与文件等发送允许后再交付，未知结果不重发。
- 工作台登录、SSH、MCP 和执行机权限仍由 MaiWork 与相应服务管理。

配置样例见 [recommended.toml](recommended.toml)。不要同时从工作台和 Host WebUI 保存同一份插件配置。

## 验证与升级

适配及相关上游测试：

```bash
python integrations/maiwork/tests/run.py --source ../MaiWork-adapted --output ../maiwork-test-results
```

原生组合测试还需要已审查 MaiWeave、组装 Host、连接器及工作区参测插件：

```bash
python tools/run_native.py --workspace .. --host ../control-build/host --adapter ../control-build/adapter --maiweave ../MaiWeave --maiwork ../MaiWork-adapted --output ../maiwork-native-results
```

外部模型与 QQ 使用本地替身。真实账号、Debian 执行隔离和长期运行需单独验证。升级先检查上游差异、重建并测试，再更新版本记录；不能直接用上游源码覆盖适配包。

停机备份代码、配置、数据库和工作区后更新，回滚使用匹配组合。适配补丁与新增模块采用 AGPL-3.0-or-later，保留上游来源与许可证。
