# 实例设置

从官方源码安装请看 [README 快速开始](../README.md#快速开始)。安装器会把 QQ 连接器放进所选实例的 `plugins/`，并在首次配置时创建 `config/behavior_control.json`。已有连接器可以沿用原目录名、`config.toml`、地址和端口。

## 启用生活、身份和群静音

1. 按 [MaiWeave](plugins/maiweave.md) 设置角色与作息，在 [MaiIdentity](plugins/maiidentity.md) 填自己的管理员账号，让 [MaiHush](plugins/maihush.md) 使用这份名单。
2. 启动 MaiBot，确认三个插件和 SnowLuma 连接器已加载。在安装时指定的群正常聊天，再用管理员账号发送 `/maihush mute 1m`，观察群静音和恢复发言。
3. 从[插件清单](plugins.md)选择其他插件。增加插件无需重新安装程序修改。

安装器创建的配置包含所填的群和机器人自己的 QQ 空间。以后增加受管群，在实例的 `config/behavior_control.json` 中复制一个 `group` 项，修改 `target_id` 后重启。MaiHush 默认管理全部 QQ 群。只有选用 Hush 群白名单时才需要在 Hush 再加群号，并留意排除名单。私聊、多账号和后台权限见[更多配置](configuration.md)。

## 从成品包安装

先停机备份。用包内的 `host/` 运行 MaiBot，并指定原来的实例目录。将包内 `plugins/` 中需要的插件和 `adapter/` 连接器装入实例的 `plugins/`。每个插件只保留一份；已有连接器请保留原配置和数据，先备份再替换代码。

已有 `config/behavior_control.json` 时继续使用。首次设置可从 `maintenance/behavior_control.example.json` 复制到该路径，将 `123456789` 替换成机器人 QQ，`987654321` 替换成受管群号，再按上节启用核心插件。使用离线导出目录时，示例在导出目录顶层。

## 更新与恢复

同版本补装可以重跑快速开始命令。另一实例共用这份源码时，用 `--instance` 指定该实例。升级主程序前，准备与 MaiTogether 匹配的官方源码，按目标 Host 安装依赖。市场里的原版连接器会覆盖配套代码，更新连接器时请使用配套工具。

安装器能直接识别本版配套连接器和对应提交的完整官方连接器。若实例装的是其他版本或有手动改动，先停机，将原连接器整个备份到插件目录之外，再运行安装命令。对照新版配置恢复账号、端口与所需数据。若提示有多份连接器，先按报出的路径核对实例中应保留哪一份。

安装中报错时工具会撤回本次已写入的文件。若因断电等原因中断，先停机，恢复安装前备份的主程序、连接器和实例配置，再启动。工具在发生修改的源码或实例旁留下 `*-maitogether-backup-*` 备份目录，其中 `restore.json` 记录原位置、修改项和新建项。只恢复本次改动时，将备份文件放回原位，移除清单中本次新增的文件。确认没有安装进程并完成恢复后，可删除遗留的空目录 `.maitogether-install.lock`。完整实例备份工具见[源码维护](maintenance.md#实例快照)。

使用自定义 `MAIBOT_BEHAVIOR_CONFIG` 路径的部署，可用[离线导出](maintenance.md#从源码构建)，自行把配置放入实际使用的位置。
