# MaiWeave 接口与测试

MaiTogether 直接使用[上游 MaiWeave](https://github.com/ilworkcn/MaiWeave)。安装和配置见[插件说明](../../docs/plugins/maiweave.md)。本目录只保存接口约定、审查版本和测试工具。

## 接口

Host 调用公开的 `get_life_status` v1，读取实际睡眠、临时唤醒、当前活动及查询时间。睡眠或忙碌时暂停社交动作；接口缺失、异常或状态无法确定时也暂停。

MaiWeave 通过 SDK 发送消息，通过 QQ 连接器的 `adapter.snowluma.qzone.send_qzone_msg` 发布空间。两条路径都经过最终发送检查，不要求 MaiWeave 调用私有交付接口。人物资料、亲密等级、主动交流及回执由上游维护。

## 可重复验证

[baseline.json](baseline.json) 记录已审查的完整上游提交。此记录供维护测试和打包核验使用，运行时不锁定插件提交。

在已安装 SDK 和测试依赖的环境中执行：

```bash
python integrations/maiweave/tests/run.py --source ../MaiWeave --output ../weave-test-results
python tools/run_native.py --workspace .. --host ../control-build/host --adapter ../control-build/adapter --maiweave ../MaiWeave --output ../weave-native-results
python tools/run_native.py --workspace .. --host ../control-build/host --adapter ../control-build/adapter --maiweave ../MaiWeave --maiweave-smoke --output ../weave-load-results
```

源码须为记录中的干净上游提交，输出目录须为新目录。第一项直接执行上游测试及源码打包校验，外网连接被禁止。第二项使用真实 Host、Runner 和 SDK，在隔离副本中添加测试入口来设置活动和睡眠、暂停后台循环；生活引擎、公开 API、发送与空间实现保持上游原样。第三项不添加测试入口，验证原版加载、公开状态、配置重载和卸载。模型与 QQ 均使用本地替身。

若上游测试失败，脚本保留失败结果，不跳过或改写上游测试。0.11.4 的 `test_failure_waits_and_expiry_stops_retry` 混用固定的中午时间与系统时间，可能因运行时刻而失败；另有统一时钟的诊断用例帮助区分测试误差与实际故障。主动交流的超时、部分发送处理仍有局限，使用建议见插件说明。

打包可选 `tools/package.py --maiweave-source <上游源码>`，直接复制原文件，保留 Manifest、许可证和作者信息。升级先审查最新源码及接口差异，再更新记录并重跑测试。完整组合与交付方法见[维护说明](../../docs/maintenance.md)。
