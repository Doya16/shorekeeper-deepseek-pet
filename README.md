# 守岸人 DeepSeek 桌宠

让守岸人陪你使用 **DeepSeek Harness 官方 Windows 客户端**。基于守岸人 Codex 桌宠的独立预览版，两版可以分别配置。

## 开始使用

1. 从 [DeepSeek 官网](https://www.deepseek.com/harness/) 下载 Windows 客户端，启动并登录。
2. 解压桌宠便携包，双击 **守岸人DeepSeek桌宠启动.exe**。
3. 从 DeepSeek 托盘菜单完全退出客户端。桌宠右键 → **外观、声音与迁移 → 连接 DeepSeek → 安装 / 更新 Harness 连接插件**。
4. 重新打开 Harness，开始任务。桌宠自动跟随最近活动的会话。

更新连接插件时重复第 3、4 步。无需额外填写 API Key。兼容验证目标：DeepSeek Harness 0.2.0-rc.2 / Windows x64。

## 可以做什么

- **看任务状态**：思考、查阅、编辑、执行、等你回应、完成、报错和暂停使用不同 GIF。多个会话完成后分别排队提醒。
- **搭配语音与字幕**：一个动作添加多条音频，每条单独配台词，随机播放；完整播完再切换提醒。思考默认每轮只播一次，待机可选择每次、每次启动一次或偶尔播放。
- **自由设置动画**：从三套共 83 个 GIF 中选择，或打开素材目录加入 GIF、动态 WebP、PNG、JPG/JPEG；设置速度、循环、单次播放及结束后的去向。
- **调整大小**：Ctrl + 滚轮缩放桌宠；拖动气泡或余额条左右边缘调整尺寸；字体、字号和气泡宽度可预览，随桌宠一起缩放。
- **桌面互动**：摸头、双击、拖动、放下、悬停、投喂均可单独绑定 GIF、音频和气泡。
- **查看账户余额**：底部显示充值与赠送余额合计；右键刷新，悬停查看币种与明细。DeepSeek 按金额显示，不换算成百分比；星号表示缓存，未连接显示 `--`。
- **随客户端启动**：连接设置中勾选随 DeepSeek 启动桌宠。托盘点击唤醒或隐藏。
- **保存与换电脑**：修改自动保存，可导出配置素材包或包含运行程序的便携完整包。GIF、气泡、字体、语音和全部桌宠设置一起携带。

![语音触发频率](docs/demo/voice-frequency.png)
![连接与启动设置](docs/demo/startup-setting.png)

## 换电脑

桌宠右键 → **外观、声音与迁移 → 保存与迁移 → 导出 Windows 便携完整包**。
在新电脑解压，安装并登录官方 Harness，启动桌宠，再在连接设置中安装连接插件。登录信息和聊天记录不在桌宠包内。

也可以导入原 Codex 版的配置素材包，继续使用自己的 GIF、声音、字幕、字体和动画设置；DeepSeek 的连接路径单独设置。

## 当前预览版说明

- 面向官方 Harness 桌面客户端；网页版普通 DeepSeek 聊天不在本版连接范围。
- 安装插件后新开始的任务会出现在桌宠会话列表，列表用“DeepSeek 会话”编号显示。
- “思考”表示任务处理阶段；气泡展示你设置的台词和字幕。
- 尚未发布 DeepSeek 版 GitHub 下载页；原版项目见 [守岸人 Codex 桌宠](https://github.com/Doya16/shorekeeper-codex-pet)。

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
