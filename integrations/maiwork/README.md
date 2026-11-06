# MaiWork 配套适配

让 [MaiWork](https://github.com/CharTyr/MaiWork) 处理任务、组织多个 Agent、使用 Skill 和 MCP，并通过工作台管理进度与成品。生活状态由 MaiWeave 提供，群静音由 MaiHush 管理，消息审批使用 MaiIdentity 管理员名单。

基于 MaiWork **0.15.3**，适配版本 **1.1.0**。需要 MaiTogether **0.3.2**、Host **1.3.19**、SDK **2.21.0** 和配套 QQ 连接器 **1.1.13**。固定源码版本见 [baseline.json](baseline.json)。

## 安装

先按 MaiTogether 主文档安装 Host 和 QQ 连接器修改，再安装 MaiWeave、Identity、Hush。停机备份原配置、数据和工作区；首次请使用单个 QQ 账号和测试群。

在 MaiTogether 目录执行，Windows PowerShell 与 Linux 均可使用：

```shell
git clone https://github.com/CharTyr/MaiWork.git MaiWork-upstream
python integrations/maiwork/build.py --source MaiWork-upstream --output MaiWork-adapted
```

构建工具读取固定提交，不使用检出目录的未提交文件。将生成的 `MaiWork-adapted` 放入 MaiBot 插件目录；同一插件只保留一份。插件 ID、上游版本和许可证保持不变，适配记录在 `maitogether-build.json`。输出目录必须不存在，补丁冲突时构建会停止。

## 首次配置

参考 [recommended.toml](recommended.toml)，在自动生成的配置中填写服务群。随后打开 MaiWork 工作台，配置模型端点，并在“专岗”页面为主模型选择模型。

- `together.enabled = true`：启用配套联动。接口缺失或异常时暂停相关操作，不自动退回原发送方式。
- `together.life_provider = "maiweave"`：按推荐配置显式选择生活后端，同时填写 Host 的 `life_provider`，见 [MaiWeave 接入](../../docs/maiweave.md)。`life_max_age_seconds` 默认 180 秒，与 Host 保持一致。
- `together.public_publish = false`：不向 here.now 上传任务网页、附件回退或续期内容。成品留在工作台，普通 QQ 文件交付仍可用。开启意味着允许这些内容公开，持有链接的人可能访问。
- `console.herenow_share` 只管群友页面分享，不能替代上面的公开发布设置。
- `/mw 批准`、`/mw 拒绝` 使用 Identity 的管理员名单；取消任务仍允许发起人和群管理，Identity 管理员也可取消。任务只能在所属群处理。
- 工作台继续使用 MaiWork 自己的登录与权限，不与 Identity 共用密码。
- MCP 必须明确填写工具白名单；空名单不导入工具。不要配置能任意管理生产服务器的凭据。

在 MaiTogether 的 `behavior_control.json` 中，把 `chartyr.maiwork` 加入该测试群的 `autonomous_plugins`，并使用 `life`、`hush` 提供者。不要顺带配置跨群权限或管理操作豁免。

首次关闭自动审核、个人主动推送、群空间管理和临时云机器。执行命令可用 MaiWork 已有 SSH 功能连接独立机器；无需安装 DSH 连接插件。不要为了本机执行而把生产 MaiBot 改成 root。

## 睡眠、静音与交付

睡眠或生活状态不可用时，不接入新的工作判断、不启动新的任务和自动模型工作。收到的消息仍留在宿主聊天记录中，旧命令不会由本适配排队重放；醒来后需要处理的任务可重新发起。

已经开始执行的获批任务可以继续计算、保存成品；通知和交付等生活状态允许后再发。群静音约束发送，不取消已获批的计算任务。新进度会替代同一任务尚未发送的旧进度，最终成品不会被合并删除。

发送被睡眠、静音或策略故障阻止时，发件箱保留记录并稍后检查。已提交但回执未知、部分完成的操作标为待核对，不自动重发或改走公开网页。管理员应先确认平台实际结果，再决定是否重新交付。

MaiWork 自己的免打扰时段仍生效。若生活状态已允许交付却仍未发送，请同时查看 MaiWork 的群推送设置和发件箱原因。

## 范围与维护

`modules/maiwork/together.py` 的 `Together.available()` 读取配置指定的生活后端，不会失败后改查其他插件。MaiWeave 状态规则从 Host 的 `life_status.py` 原样收录到构建结果；不依赖运行 Host 的 Python 导入路径。兼容后端的设置见 [Life Provider 维护说明](../../docs/life-provider.md#兼容与回滚)。

该查询用于新任务、模型工作、发件箱和网页发布。无群目标的任务按全局生活状态判断；有群目标的任务还检查服务群范围。它不授予发送或管理权限。MaiWeave 的睡眠状态缺口仍会导致部分空闲时间暂停工作；不能关闭安全联动来消除这一限制。已有任务收尾、管理员检查和 `behavior.send_v1` 交付保持原样。

本适配提供 QQ 交付、生活状态和消息审批联动，不把 SSH、MCP、独立 HTTP 变成安全沙箱。任务获批也不代表任意外部写操作获权；这些能力需依靠执行机隔离和服务端权限。多 QQ 账号、Debian 执行隔离、真实账号和长期运行需另行验收。

维护内容是 `maiwork.patch`、`modules/` 和构建时共享的状态解析模块，不维护第二份完整 MaiWork。升级时先更新固定提交，检查补丁冲突、重新构建，再跑隔离验收；不能直接用上游覆盖适配包。

在安装了插件依赖、pytest 和 pytest-asyncio 的测试环境中运行：

```shell
python integrations/maiwork/tests/run.py --source MaiWork-adapted --output ../maiwork-test-results
```

该命令运行适配测试及相关上游测试，禁止外部网络连接。原生 Host 联调使用 `tools/run_native.py --maiwork <适配目录>`，还需指定 `--workspace`、`--host`、`--adapter` 和新的 `--output` 目录；工作区应包含本项目测试脚本要求的核心插件及社区源码。模型与 QQ 均使用本地替身，不使用真实账号。

配置编辑期间只使用一个入口，避免 MaiWork 工作台与 Host WebUI 同时保存。上游配置写入仍有非原子覆盖限制；更新前停机备份，回滚时恢复匹配的代码、配置与数据。

上游采用 AGPL-3.0-or-later，构建结果保留原许可证与来源。部署包不包含运行配置、账号、数据库或日志。
