# 安装与设置

从已经能运行的 MaiBot 开始。主程序修改和 QQ 连接器只需安装一次，之后按需添加插件。

## 1. 安装主程序修改和 QQ 连接器

先停止 MaiBot，备份源码、插件、配置和数据。在 MaiTogether 目录运行：

```powershell
# Windows PowerShell
python tools/prepare.py --host "../MaiBot" --output "../MaiTogether-ready" --apply
```

```bash
# Linux
python3 tools/prepare.py --host ../MaiBot --output ../MaiTogether-ready --apply
```

把 `../MaiBot` 改成已有的主程序源码路径，输出目录须是一个新目录。需要 Git 和 Python 3.11 以上版本；运行 MaiBot 使用它原有的 Python 环境。

命令会检查主程序版本，下载并制作配套 QQ 连接器，再备份和修改 Host 源码。**当前适用 MaiBot 1.4.3**；版本不同或源码已有修改时会停止，不会自动降级、重置源码或改动数据库。

将输出的 `adapter/` 安装到所选 Bot 实例的 `plugins/` 中：

- 首次安装：整个目录复制过去，目录名可改为 `MaiBot-SnowLuma-Adapter`。
- 已有 SnowLuma 连接器：备份后，用输出目录中的文件覆盖原连接器代码，保留 `config.toml` 和运行数据。同一实例只保留一份连接器。

继续使用原来的 SnowLuma 地址、端口和账号设置。无需另备一套干净的 MaiBot，也无需先装原版连接器再打补丁。主程序已经装过修改时，不要重复运行安装命令；升级方法见[更新与恢复](maintenance.md#更新与恢复)。

## 2. 选择插件

生活和静音组合使用 [MaiWeave](plugins/maiweave.md)、[MaiHush](plugins/maihush.md)、[MaiIdentity](plugins/maiidentity.md)。按各自页面设置作息、受管理群和管理员，其余从[插件清单](plugins.md)按需选择。

插件仍使用自己的安装方式、WebUI 和配置文件。无需为每个插件重复安装 Host 修改或运行开发测试。

## 3. 填写机器人账号和群号

把输出目录中的 `behavior_control.example.json` 复制到 **Bot 实例的** `config/behavior_control.json`。将所有 `123456789` 替换为机器人自己的 QQ 号，将群聊项的 `987654321` 替换为群号：

```json
"account_id": "机器人自己的QQ号",
"target_id": "要管理的群号"
```

示例还包含一项 `chat_type: "space"`，其中 `account_id` 和 `target_id` 都填机器人 QQ 号，用于 MaiWeave 空间发布。其他设置先保持示例值。管理多个群时，只复制 `chat_type: "group"` 的项并分别填写群号；MaiHush 里也添加这些群。文件是 JSON，不支持注释。

实例目录就是这个 Bot 的 `config/`、`data/`、`plugins/` 所在目录。通过 `maibot run --directory ...` 启动时使用指定目录；直接从源码启动且未设置实例路径时，通常就是主程序目录。

示例已包含[插件清单](plugins.md)中需要后台发送的插件，回复守卫除外，无需逐个添加。不安装或不开启对应插件功能，就不会因此产生动作；发送仍受睡眠和静音限制。

启动 MaiBot 后，确认三个核心插件和 QQ 连接器已加载。在一个已配置的群里正常聊天，再用管理员账号发送 `/maihush mute 1m`，观察静音和恢复是否符合预期。

没有这份配置时，统一发送检查默认关闭。**已经开启时，必要插件故障会阻止发送**，原因和处理方法见[常见问题](troubleshooting.md)。私聊、多账号和其他设置见[更多配置](configuration.md)。
