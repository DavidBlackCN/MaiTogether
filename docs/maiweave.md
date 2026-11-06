# MaiWeave 接入

MaiWeave 提供日常生活和主动交流，MaiTogether 通过 `get_life_status@1` 查询状态，在需要休息时暂停对话和动作。

当前状态接口尚不能区分部分正常空闲与临时唤醒结束后的回睡间隙，遇到这两种情况都会暂停。进展见 [Issue #2](https://github.com/ilworkcn/MaiWeave/issues/2)。部署前请先在测试实例确认睡眠与唤醒体验。

## 组合与配置

安装原版 MaiWeave、MaiIdentity 和 MaiHush。生活作息和主动交流在 MaiWeave 中设置，固定身份与管理员在 MaiIdentity 中设置，受管群在 MaiHush 中设置。

在测试实例的 `behavior_control.json` 顶层添加：

```json
"life_provider": {
  "plugin_id": "ilworkcn.maiweave",
  "api": "get_life_status",
  "version": "1",
  "protocol": "maiweave_status_v1",
  "max_age_seconds": 180
}
```

目标使用 `"providers": ["life", "hush"]`，群号、机器人账号和范围仍须显式配置。需要 MaiWeave 主动发言时，只在允许的目标将 `ilworkcn.maiweave` 加入 `autonomous_plugins`。没有自动发现目标、跨群豁免或失败回退。配置后重启 Host。

MaiWork 适配版 1.1.0 另外配置：

```toml
[together]
enabled = true
life_provider = "maiweave"
life_max_age_seconds = 180
public_publish = false
```

Host 与 MaiWork 的状态最大年龄应相同，且大于 MaiWeave 的生活更新间隔。默认适用于 60 秒更新间隔；`updated_at` 是状态推进时间，不是查询时间，也不能证明所有后台任务健康。

## 当前规则

| 情况 | 认知与普通对话 | 主动社交与新工作 |
| --- | --- | --- |
| 明确清醒的活动、有效唤醒时段 | 允许 | 允许，仍受静音和权限约束 |
| 工作、学习、出行 | 允许 | 暂停 |
| 按作息睡眠且未临时唤醒 | 暂停 | 暂停 |
| 按作息运行，无活动且无有效唤醒期限 | 暂停，状态不明确 | 暂停，状态不明确 |
| 明确配置为全天候，正常空闲 | 允许 | 允许 |
| 接口缺失、超时、版本不符、未就绪、引擎关闭或状态过期 | 暂停 | 暂停 |

全天候模式须来自 MaiWeave 的真实配置，不能用来绕过睡眠缺口。忙碌规则只按公开活动类别判断，不宣称覆盖 MaiWeave 内部所有临时安排。活动跨过结束时间后需重新查询，不复用先前的许可。

状态只用于行为判断。API 没有提供公开分享范围，不应将活动标题、地点或未来计划直接作为空间发帖素材。

## 睡眠、唤醒与工作

认知暂停保留原始聊天记录，不启动正常 Planner／Replyer，也不把睡眠消息补入自动记忆。接收 Hook 仍运行，MaiWeave 的原生关键词唤醒可以在认知检查前生效。需要 Planner 理解后才调用唤醒 Tool 的表达，在睡眠暂停时不会生效；亲密关系也不授予 Identity 管理权限。

MaiWork 的全局后台任务直接读取全局生活状态，不虚构群目标。指定群的任务还检查服务群范围。已开始的获批任务可以收尾；通知、文件交付仍受最终发送检查，未知结果不重发。生活状态查询不是发送许可。

Host 的认知暂停不等于关闭 MaiWeave 的生活循环、梦境或其他独立后台功能；这些能力仍按插件自己的配置运行。

## 更新与回滚

每轮开发先获取 MaiWeave 默认分支最新源码，再审查 API 与生命周期变化。记录准确提交后运行测试；交付前再次比较远端提交。版本号相同不代表源码相同，不将旧提交测试套用到新提交。

当前记录见 [baseline.json](../integrations/maiweave/baseline.json)。验证器要求源码干净且提交一致，不会静默使用一个新版本。

```shell
python tools/run_native.py --workspace .. --host <组装Host> --adapter <组装连接器> --maiweave <已审查MaiWeave源码> --output <新的测试目录>
```

加 `--maiwork <已构建MaiWork适配目录>` 可验证工作联动。完整矩阵使用 `tools/validate.py` 的同名参数。原生测试在隔离副本中注入状态夹具、暂停自主后台循环，真实 API／引擎／Hook 保持原实现；模型与 QQ 使用本地替身。

实验交付包可用 `tools/package.py --workspace .. --output <新的输出目录> --maiweave-source <已审查MaiWeave源码> --maiwork-source <固定MaiWork源码>` 生成。包中包含原版 MaiWeave、Identity、Hush 和适配 MaiWork，不包含运行数据或测试夹具。

更新前备份代码、配置与数据库；回滚时恢复匹配组合，Host 与 MaiWork 的生活后端设置须一致。操作方法见[备份和恢复](maintenance.md#备份和恢复)。
