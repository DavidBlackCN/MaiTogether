# MaiWeave 适配

保留 MaiWeave 的生活引擎，补充可靠交付与人物资料范围。上游版本和提交见 [baseline.json](baseline.json)，使用说明见 [MaiWeave 插件页](../../docs/plugins/maiweave.md)。

## 构建

在 MaiTogether 目录执行，Windows 与 Linux 使用相同命令：

```bash
git clone https://github.com/ilworkcn/MaiWeave.git ../MaiWeave-upstream
python integrations/maiweave/build.py --source ../MaiWeave-upstream --output ../MaiWeave-adapted
```

把生成的 `MaiWeave-adapted` 作为 MaiWeave 插件安装到 Bot 实例。它保留上游插件 ID、版本、许可证和工作区，同一实例只安装一份。需要配套 MaiTogether Host，交付接口不可用时不会退回普通发送。

## 适配内容

- 主动分享使用详细交付回执；未知、部分发送及提交期间中断的操作等待核对，不自动重发。工作区“交流与运行详情”提供核对按钮。
- 日记通过 SnowLuma 发布文字空间动态，发布前检查当前账号与生活状态。群静音不限制个人空间。
- 固定身份提示交给 MaiIdentity。MaiWeave 的聊天上下文不再注入自动推断的关系称呼，叫醒与影响日程只使用手动亲密等级。
- 用户近况默认只用于来源聊天，可通过“跨聊天共享近况”显式开启共享。

`maiweave.patch` 只修改必要入口和状态记录，`modules/` 保存独立交付逻辑。`maitogether-build.json` 记录来源及文件哈希。更新时重新审查上游差异，应用补丁、运行测试后再更新版本锁；不要直接覆盖适配包。

适配代码沿用上游 GPL-3.0-only。配置、数据库和运行日志不包含在源码交付中。

## 维护测试

在已安装 SDK 和测试依赖的环境中执行：

```bash
python integrations/maiweave/tests/run.py --source ../MaiWeave-adapted --output ../weave-test-results
```

输出目录须为新目录。测试覆盖交付、隐私、身份提示及受影响的上游生活功能，并阻止外网连接。真实 Host 组合测试见[维护说明](../../docs/maintenance.md)。
