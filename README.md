# 守岸人 DeepSeek 桌宠

**v0.5.2**：锁定后，角色和底部额度／余额框一起悬停淡化，透明度沿用设置；点击刷新、调整大小和解锁仍可使用。配置与素材保持不变。

让守岸人陪你使用 **DeepSeek Harness 官方 Windows 客户端**。任务进行时换表情，完成后用语音和气泡回应。

[Windows 下载](https://github.com/Doya16/shorekeeper-deepseek-pet/releases/latest) · [完整演示](https://github.com/Doya16/shorekeeper-deepseek-pet/releases/download/v0.5.1/shorekeeper-deepseek-landscape-v051-r2.mp4) · [使用指南](docs/USAGE.md) · [English](README.en.md)

![守岸人 DeepSeek 桌宠：自选表情与语音互动](docs/social/cover-landscape.jpg)

[横屏封面](docs/social/cover-landscape.jpg) · [4:3 封面](docs/social/cover-4x3.jpg) · [竖屏封面](docs/social/cover-portrait.jpg)

适用于 **Windows 10/11 x64**。完整包内置 **三套 83 个 GIF、40 个音频文件、54 组语音字幕配对和两款字体**，无需安装 Python。可与 [Codex 版](https://github.com/Doya16/shorekeeper-codex-pet) 同时使用，分别保存设置。

## 效果预览

![最新版任务互动、锁定穿透与额度刷新](docs/social/showcase.gif)

[横屏演示 · 1920×1080](https://github.com/Doya16/shorekeeper-deepseek-pet/releases/download/v0.5.1/shorekeeper-deepseek-landscape-v051-r2.mp4) · [竖屏演示 · 1080×1920](https://github.com/Doya16/shorekeeper-deepseek-pet/releases/download/v0.5.1/shorekeeper-deepseek-portrait-v051-r2.mp4)

演示对应 **v0.5.1**，时长 **03:17**。全部换成当前桌宠与设置界面，展示任务跟随、多会话完成提醒、自选素材、语音字幕、锁定穿透、快捷静音、余额刷新、大小字体、图标、启停联动、更新来源与完整迁移。横屏、竖屏分别排版。

**客户端窗口、任务、余额和新版提醒为示例；桌宠与设置为当前版本实际界面。**

| 时间 | 展示内容 |
| --- | --- |
| 00:01 | 跟随任务 |
| 00:30 | 多个会话 |
| 00:50 | 桌面互动 |
| 01:06 | 更轻巧的陪伴 |
| 01:24 | 额度与余额 |
| 01:36 | 自己搭配 |
| 02:14 | 外观与摆放 |
| 02:31 | 启停与更新 |
| 02:53 | 保存与迁移 |
| 03:09 | 下载与使用 |

![一个会话完成时，另一个继续编辑](docs/social/multi-project.jpg)

| 锁定、淡化与点击穿透 | 底部余额框刷新反馈 |
| --- | --- |
| ![悬停小锁与点击穿透](docs/social/lock-click-through.jpg) | ![余额框内显示刷新中](docs/social/balance-refresh.jpg) |

## 开始使用

1. 从 [DeepSeek 官网](https://www.deepseek.com/harness/) 下载 Windows 客户端，启动并登录。
2. 下载 **Shorekeeper-DeepSeek-Windows-v0.5.2.zip**，完整解压，双击 **守岸人DeepSeek桌宠启动.exe**。
3. 从 DeepSeek 托盘菜单完全退出客户端。桌宠右键 → **设置 → 连接 DeepSeek → 安装 / 更新 Harness 连接插件**。
4. 重新打开 Harness，开始任务。桌宠自动跟随最近活动的会话。

更新连接插件时重复第 3、4 步。无需额外填写 API Key。兼容验证目标：DeepSeek Harness 0.2.0-rc.2 / Windows x64。

## 图标与桌面快捷方式

- 默认图标在守岸人右下角显示 APP 小标：**Codex 使用黑白 GPT 图标，DeepSeek 使用蓝色鲸鱼**。
- 在 **设置 → 桌面与声音 → 底部栏与托盘图标** 中选择 **纯净图标 / APP 小标**，立即生效，选择随配置保存和迁移。
- 完整解压后，首次启动 Windows 版会自动创建桌面快捷方式。误删后，在 **设置 → 保存与迁移 → 创建桌面快捷方式** 中重新创建。
- 换电脑后先完整解压、启动一次；快捷方式指向新电脑上的程序位置。

![图标样式与桌面快捷方式设置](docs/demo/shortcut-settings.png)

## 设置、静音与锁定

右键桌宠或托盘 → **设置…**，在同一个窗口调整 **字体与大小、交互工作室、桌面与声音、保存与迁移、连接、版本与更新**。GIF、语音字幕、播放频率、启动联动和更新检查都在这里。

- **安静陪伴（静音）**：立即停止当前和待播声音，同时暂停自动语音与试听；取消后恢复原音量，不补播静音期间的声音。
- **顶部小锁**：鼠标移到角色身上时，顶部居中会显示小锁，点击即可锁定／解锁；移开鼠标后隐藏，悬停显示“点击锁定”或“点击解锁”。锁定后，点击角色区域可穿透到下方窗口；鼠标移到角色上时自动淡化，移开恢复。小锁仍可解锁，余额框仍可点击刷新；任务动画与完成提醒继续。
- **悬停透明度**：在「设置 → 桌面与声音」调整锁定时的淡化程度；小锁的大小与透明度也可分别设置。
- **余额刷新**：鼠标移到余额框内显示手形，点击后框内显示“刷新中…”，读完后恢复最新数值。失败时短暂显示“刷新失败”，随后保留上次读数；重复点击不会叠加请求。拖动左右边缘仍可调整大小，锁定后暂停拖边缩放。
- **简洁菜单**：设置集中在「设置…」；关闭程序请选择「关闭守岸人」。解锁也可从托盘进入「设置 → 桌面与声音」。
- 两个开关都会自动保存，导出配置素材包或便携完整包时一起携带。旧版开启的“安静陪伴”会转为静音；新加入的锁定默认关闭。

小锁大小可在 **设置 → 桌面与声音** 调整，之后随桌宠整体等比例缩放。

<img src="docs/demo/quota-refresh.png" width="180" alt="余额框内刷新反馈（示例）">

<img src="docs/demo/pet-lock.png" width="180" alt="桌宠顶部小锁（示例）">

![统一设置中的桌面与声音选项](docs/demo/unified-settings.png)

## 随客户端退出

在 **设置 → 连接 DeepSeek** 中，可分别勾选 **随 DeepSeek 启动桌宠** 和 **随 DeepSeek 完全退出而关闭**。

退出联动默认开启：客户端完全退出约 8–10 秒后关闭桌宠。关闭窗口但仍在托盘运行时，桌宠继续陪伴；有多个客户端实例时，最后一个退出后才关闭。短暂重启不会立即关掉桌宠。先手动打开桌宠、尚未启动客户端时，桌宠会等待客户端运行。

![连接与退出联动](docs/demo/connection-settings.png)

## 检查更新与保留配置升级

当前版本：**v0.5.2**。每次启动桌宠后，自动在后台检查正式版本；发现新版才弹出提示。右键 → **设置 → 版本与更新 → 立即检查更新** 可随时手动检查。

在 **设置 → 版本与更新** 中，可关闭启动检查、立即检查或恢复已忽略版本的提醒。新版提示支持 **打开更新页面、备份配置与素材、稍后提醒、忽略此版本**。网络检查失败不会打断桌宠。

**更新来源**可选 **自动选择／GitHub 官方源／镜像加速（中国大陆网络）**。自动模式先尝试 GitHub，超时或连接失败时切换镜像；手动固定来源后只使用该来源。更新窗口会显示本次来源，并提供完整包、程序补丁与校验文件的下载按钮。

镜像加速由第三方 [GH-Proxy](https://gh-proxy.com/docs/github-accelerator) 提供，仅访问公开版本信息和下载文件。镜像可能存在同步延迟，可切回 GitHub 检查。选择会随配置保存和迁移。

![版本与更新设置](docs/demo/update-settings.png)

**更新提醒不会自动下载安装。** 按当前版本选择下载方式：

| 当前情况 | 如何更新 |
| --- | --- |
| 已有 v0.5.1 | 下载 [v0.5.2 程序补丁](https://github.com/Doya16/shorekeeper-deepseek-pet/releases/download/v0.5.2/Shorekeeper-DeepSeek-Settings-Patch-v0.5.2.zip)，退出桌宠，将补丁解压到原目录并覆盖同名文件，然后重新启动 |
| 首次使用，或安装了其他旧版 | 下载 [v0.5.2 完整包](https://github.com/Doya16/shorekeeper-deepseek-pet/releases/download/v0.5.2/Shorekeeper-DeepSeek-Windows-v0.5.2.zip)，解压到新目录；已有配置时，再导入自己导出的配置与素材 ZIP |

程序补丁保留 **GIF / 图片、音频、气泡字幕、字体和个人设置**。更新前可在 **保存与迁移 → 导出配置与素材包（ZIP）** 留一份备份。程序补丁直接解压覆盖，不在设置中导入。

## 可以做什么

- **看任务状态**：思考、查阅、编辑、执行、等你回应、完成、报错和暂停使用不同 GIF。多个会话完成后分别排队提醒。
- **搭配语音与字幕**：一个动作添加多条音频，每条单独配台词，随机播放；完整播完再切换提醒。思考默认每轮只播一次，待机可选择每次、每次启动一次或偶尔播放。
- **自由设置动画**：从三套共 83 个 GIF 中选择，或打开素材目录加入 GIF、动态 WebP、PNG、JPG/JPEG；设置速度、循环、单次播放及结束后的去向。
- **调整大小**：Ctrl + 滚轮缩放桌宠；拖动气泡或余额条左右边缘调整尺寸；字体、字号和气泡宽度可预览，随桌宠一起缩放。
- **桌面互动**：摸头、双击、拖动、放下、悬停、投喂均可单独绑定 GIF、音频和气泡。
- **查看账户余额**：底部显示充值与赠送余额合计；右键刷新，悬停查看币种与明细。DeepSeek 按金额显示，不换算成百分比；星号表示缓存，没有可用余额时显示 `--`。
- **随客户端启动**：连接设置中勾选随 DeepSeek 启动桌宠。托盘点击唤醒或隐藏。
- **更新提醒**：每次启动检查新版，支持手动检查、稍后提醒和忽略版本。
- **声音与托盘**：音量合成器显示「守岸人 · DeepSeek」，可单独调音量；托盘提示「守岸人 · DeepSeek · 点击唤醒/隐藏」。
- **保存与换电脑**：修改自动保存，可导出配置素材包或包含运行程序的便携完整包。GIF、气泡、字体、语音和全部桌宠设置一起携带。

![语音触发频率](docs/demo/voice-frequency.png)
![连接与启动设置](docs/demo/startup-setting.png)

## 自定义入口

右键桌宠 → **设置 → 交互工作室**，先选择动作，再设置表情、气泡和语音。

| 想修改什么 | 在哪里操作 |
| --- | --- |
| 为每个动作选择 GIF 或图片 | GIF 素材 → 点击缩略图 |
| 添加自己的素材 | 导入图片；或打开素材目录 → 放入文件 → 刷新素材 |
| 循环、速度、播完停留和下一状态 | 播放与切换 |
| 多条语音随机抽取，每条单独配字幕 | 语音与配对气泡 → 添加多个文件 → 选中一条编辑 |
| 只显示选中语音的配对台词 | 气泡与字体 → 气泡内容 → 自定义音频+字幕 |
| 调整气泡宽度与余额条大小 | 右键 → 设置 → 字体与大小；或拖动气泡、余额条左右边缘 |

| 自选表情 | 语音与配对字幕 |
| --- | --- |
| ![GIF 素材列表](docs/demo/gif-library-panel.png) | ![多条音频逐条配对台词](docs/demo/voice-pairs-panel.png) |

支持 GIF、动画 WebP、PNG、JPG/JPEG、静态 WebP；语音支持 WAV、MP3、OGG、FLAC、M4A、AAC；字体支持 TTF、OTF、TTC。音频旁放置同名 UTF-8 TXT，可在导入时读取台词。不添加音频也能使用。

## 换电脑

![配置和素材一起打包](docs/social/portable-profile.jpg)

桌宠右键 → **设置 → 保存与迁移 → 导出 Windows 便携完整包**。
在新电脑解压，安装并登录官方 Harness，启动桌宠，再在连接设置中安装连接插件。登录信息和聊天记录不在桌宠包内。

也可以导入原 Codex 版的配置素材包，继续使用自己的 GIF、声音、字幕、字体和动画设置；DeepSeek 的连接路径单独设置。

## 适用范围

- 面向官方 Harness 桌面客户端；网页版普通 DeepSeek 聊天不在本版连接范围。
- 安装插件后新开始的任务会出现在桌宠会话列表，列表用“DeepSeek 会话”编号显示。
- “思考”表示任务处理阶段；气泡展示你设置的台词和字幕。
- v0.1.0 已在 Harness **0.2.0-rc.2** 上验证真实任务、等待回应、恢复、手动中止和多会话分别完成提醒。完整包也经过换目录启动、导入和再次导出检查。详见 [验证记录](docs/VALIDATION.md)。

## 素材来源与感谢

表情包来自 [鸣潮表情包站](https://emoji.wuwa.games/)。表情包众筹 QQ 群：**1079834905**。
感谢所有为该项目表情包众筹投资的守岸人厨子们。
字体、角色语音与其他素材说明见 [THIRD_PARTY.txt](THIRD_PARTY.txt)。

## 从源码运行

安装 Python 3.11+，在项目目录执行：

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python tools\run_pet.py
```

```powershell
.venv\Scripts\python -m unittest discover -s tests
node --test integrations/deepseek/state.test.js
.venv\Scripts\python tools\build_portable.py
```
