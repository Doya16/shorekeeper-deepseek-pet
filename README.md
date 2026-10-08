# 守岸人 DeepSeek 桌宠

让守岸人陪你使用 **DeepSeek Harness 官方 Windows 客户端**。任务进行时换表情，完成后用语音和气泡回应。

[Windows 下载](https://github.com/Doya16/shorekeeper-deepseek-pet/releases/latest) · [完整演示](https://github.com/Doya16/shorekeeper-deepseek-pet/releases/download/v0.1.0/shorekeeper-landscape-deepseek-v010.mp4) · [使用指南](docs/USAGE.md) · [English](README.en.md)

![守岸人 DeepSeek 桌宠：自选表情与语音互动](docs/social/cover-landscape.jpg)

[横屏封面](docs/social/cover-landscape.jpg) · [4:3 封面](docs/social/cover-4x3.jpg) · [竖屏封面](docs/social/cover-portrait.jpg)

适用于 **Windows 10/11 x64**。完整包内置 **三套 83 个 GIF、40 个音频文件、54 组语音字幕配对和两款字体**，无需安装 Python。可与 [Codex 版](https://github.com/Doya16/shorekeeper-codex-pet) 同时使用，分别保存设置。

## 看看她能做什么

![任务状态与多会话完成提醒](docs/social/showcase.gif)

[横屏演示](https://github.com/Doya16/shorekeeper-deepseek-pet/releases/download/v0.1.0/shorekeeper-landscape-deepseek-v010.mp4) · [竖屏演示](https://github.com/Doya16/shorekeeper-deepseek-pet/releases/download/v0.1.0/shorekeeper-portrait-deepseek-v010.mp4)

演示录制于 **v0.1.0**，约两分钟：任务状态、多会话提醒、拖动与摸头、自选 GIF、语音字幕配对、声音频率、大小调整、账户余额、连接与打包迁移。视频中的 Harness 窗口、项目、对话与余额为模拟示例；桌宠和设置展示录制版本的实际界面。启动检查更新等后续功能见下方说明。

![一个会话先完成，另一个继续编辑](docs/social/multi-project.jpg)

## 开始使用

1. 从 [DeepSeek 官网](https://www.deepseek.com/harness/) 下载 Windows 客户端，启动并登录。
2. 下载 **Shorekeeper-DeepSeek-Windows-v0.1.2.zip**，完整解压，双击 **守岸人DeepSeek桌宠启动.exe**。
3. 从 DeepSeek 托盘菜单完全退出客户端。桌宠右键 → **外观、声音与迁移 → 连接 DeepSeek → 安装 / 更新 Harness 连接插件**。
4. 重新打开 Harness，开始任务。桌宠自动跟随最近活动的会话。

更新连接插件时重复第 3、4 步。无需额外填写 API Key。兼容验证目标：DeepSeek Harness 0.2.0-rc.2 / Windows x64。

## 检查更新与保留配置升级

当前版本：**v0.1.2**。每次启动桌宠后，自动在后台检查 GitHub 正式版本；发现新版才弹出提示。右键 → **检查更新…** 可随时手动检查。

在 **外观、声音与迁移 → 版本与更新** 中，可关闭启动检查、立即检查或恢复已忽略版本的提醒。新版提示支持 **打开更新页面、备份配置与素材、稍后提醒、忽略此版本**。网络检查失败不会打断桌宠。

![版本与更新设置](docs/demo/update-settings.png)

**更新提醒不会自动下载安装。** 按当前版本选择下载方式：

| 当前情况 | 如何更新 |
| --- | --- |
| 已有 v0.1.1 | 下载 [v0.1.2 程序补丁](https://github.com/Doya16/shorekeeper-deepseek-pet/releases/download/v0.1.2/Shorekeeper-DeepSeek-Update-Check-Patch-v0.1.2.zip)，退出桌宠，将补丁解压到原目录并覆盖同名文件，然后重新启动 |
| 首次使用，或安装了其他旧版 | 下载 [v0.1.2 完整包](https://github.com/Doya16/shorekeeper-deepseek-pet/releases/download/v0.1.2/Shorekeeper-DeepSeek-Windows-v0.1.2.zip)，解压到新目录；已有配置时，再导入自己导出的配置与素材 ZIP |

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

右键桌宠 → **交互工作室**，先选择动作，再设置表情、气泡和语音。

| 想修改什么 | 在哪里操作 |
| --- | --- |
| 为每个动作选择 GIF 或图片 | GIF 素材 → 点击缩略图 |
| 添加自己的素材 | 导入图片；或打开素材目录 → 放入文件 → 刷新素材 |
| 循环、速度、播完停留和下一状态 | 播放与切换 |
| 多条语音随机抽取，每条单独配字幕 | 语音与配对气泡 → 添加多个文件 → 选中一条编辑 |
| 只显示选中语音的配对台词 | 气泡与字体 → 气泡内容 → 自定义音频+字幕 |
| 调整气泡宽度与余额条大小 | 右键 → 调整大小；或拖动气泡、余额条左右边缘 |

| 自选表情 | 语音与配对字幕 |
| --- | --- |
| ![GIF 素材列表](docs/demo/gif-library-panel.png) | ![多条音频逐条配对台词](docs/demo/voice-pairs-panel.png) |

支持 GIF、动画 WebP、PNG、JPG/JPEG、静态 WebP；语音支持 WAV、MP3、OGG、FLAC、M4A、AAC；字体支持 TTF、OTF、TTC。音频旁放置同名 UTF-8 TXT，可在导入时读取台词。不添加音频也能使用。

## 换电脑

![配置和素材一起打包](docs/social/portable-profile.jpg)

桌宠右键 → **外观、声音与迁移 → 保存与迁移 → 导出 Windows 便携完整包**。
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
