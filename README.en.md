# Shorekeeper DeepSeek Desktop Pet

**v0.5.2**: Locked hover now fades both the pet and its quota/balance bar. Refresh, resize, and unlock controls remain usable; settings and media are preserved.

**A companion for the official DeepSeek Harness Windows client, with custom expressions, voice clips, and speech bubbles.**

[Download for Windows](https://github.com/Doya16/shorekeeper-deepseek-pet/releases/latest) · [Watch the demo](https://github.com/Doya16/shorekeeper-deepseek-pet/releases/download/v0.5.1/shorekeeper-deepseek-landscape-v051-r2.mp4) · [User guide (Chinese)](docs/USAGE.md) · [Report an issue](https://github.com/Doya16/shorekeeper-deepseek-pet/issues) · [中文](README.md)

![Shorekeeper DeepSeek Desktop Pet: custom expressions and voice interactions](docs/social/cover-landscape.jpg)

[Landscape cover](docs/social/cover-landscape.jpg) · [4:3 cover](docs/social/cover-4x3.jpg) · [Portrait cover](docs/social/cover-portrait.jpg)

For **Windows 10/11 x64**. The complete package includes **three packs with 83 GIFs, 40 audio files, 54 voice/caption pairs, and two fonts**. No Python installation is required. It can run alongside the [Codex edition](https://github.com/Doya16/shorekeeper-codex-pet), with separate settings.

## Preview

![Current task interactions and new desktop controls](docs/social/showcase.gif)

[Landscape · 1920×1080](https://github.com/Doya16/shorekeeper-deepseek-pet/releases/download/v0.5.1/shorekeeper-deepseek-landscape-v051-r2.mp4) · [Portrait · 1080×1920](https://github.com/Doya16/shorekeeper-deepseek-pet/releases/download/v0.5.1/shorekeeper-deepseek-portrait-v051-r2.mp4)

The **03:17** walkthrough uses **v0.5.1**, with new recordings of the pet and current settings. It covers task interactions, multiple conversation notifications, custom media, lock and click-through, mute, balance refresh, sizing, app icons, client lifecycle, update sources, and complete migration. Portrait and landscape use separate layouts.

**The client window, tasks, balances and available-update notification are examples.** Pet animations and settings are rendered from the current application. The video uses Chinese labels and character voices.

| Time | Demonstration |
| --- | --- |
| 00:01 | Task states and one opening voice per turn |
| 00:30 | Separate completion notifications |
| 00:50 | Dragging, dropping, double-clicking and head pats |
| 01:06 | Hover lock, click-through, fade and mute |
| 01:24 | Visible balance refresh and account display |
| 01:36 | GIFs, playback, paired audio/captions and frequency |
| 02:14 | Sizing, fonts and app-badged icons |
| 02:31 | Client lifecycle, update notifications and download sources |
| 02:53 | Save, migration and desktop shortcuts |
| 03:09 | Download and setup |

![One conversation finishes while another continues editing](docs/social/multi-project.jpg)

| Lock and click-through | Visible balance refresh |
| --- | --- |
| ![Hover lock and fade](docs/social/lock-click-through.jpg) | ![Inline refresh state](docs/social/balance-refresh.jpg) |

## Get started

1. Install the Windows client from the [official DeepSeek Harness website](https://www.deepseek.com/harness/), open it, and sign in.
2. Download [Shorekeeper-DeepSeek-Windows-v0.5.2.zip](https://github.com/Doya16/shorekeeper-deepseek-pet/releases/download/v0.5.2/Shorekeeper-DeepSeek-Windows-v0.5.2.zip), extract it completely, and run **守岸人DeepSeek桌宠启动.exe**.
3. Fully quit Harness from its tray menu. Right-click the pet → **设置 → 连接 DeepSeek → 安装 / 更新 Harness 连接插件** (Settings → Connect to DeepSeek → Install / Update Harness Connection Plugin).
4. Reopen Harness and start a task. The pet follows the most recently active conversation.

Repeat steps 3–4 when updating the connection plugin. No additional API key is required. The tested client is **DeepSeek Harness 0.2.0-rc.2 / Windows x64**.

## App badges and desktop shortcuts

The default pet icon has a small app badge: a black-and-white GPT mark for Codex, or a blue whale for DeepSeek. Under **设置 → 桌面与声音 → 底部栏与托盘图标**, choose **纯净图标** (plain) or **APP 小标** (badged). The taskbar/window and tray icons update immediately, and the preference travels with your settings.

The extracted Windows app creates a desktop shortcut on its first normal launch. If deleted, recreate it under **设置 → 保存与迁移 → 创建桌面快捷方式**. On another computer, extract the complete package and run it once to create a shortcut pointing to its new location.

![Desktop shortcut settings](docs/demo/shortcut-settings.png)

## Settings, mute and lock

Right-click the pet or tray icon → **设置…** (Settings). One window contains size and fonts, the interaction studio, desktop and sound, save and migration, client connection, and updates.

- **安静陪伴（静音）** (Mute) immediately stops current and queued audio, and silences automatic speech and previews. Unmuting restores the original volume without replaying missed speech.
- **Top lock button:** move the pointer over the character to reveal its small lock at the top center. Click to lock or unlock; it hides when the pointer leaves. Its tooltip shows **点击锁定** (Click to lock) or **点击解锁** (Click to unlock). When locked, clicks through the character reach the window underneath. Hovering fades the character; moving away restores it. The lock remains clickable to unlock, and the balance box remains clickable to refresh. Task animations and notifications continue.
- **Hover fade:** adjust it under Settings → Desktop & audio, alongside lock-button size and transparency.
- **Balance refresh:** hovering inside the box shows a hand cursor. Click to show **刷新中…** (Refreshing…) in the box; it returns to the latest value when the read finishes. A failure briefly shows **刷新失败** (Refresh failed) before restoring the last reading. Repeated clicks are combined. The edges still resize the box while unlocked.
- **Compact menu:** use **设置…** for preferences and **关闭守岸人** to close. The tray also gives access to the lock setting.
- Both options save automatically and travel with exported settings and portable packages. The old quiet-companion option becomes mute; locking is off by default.

<img src="docs/demo/quota-refresh.png" width="180" alt="余额框内刷新反馈（示例）">

<img src="docs/demo/pet-lock.png" width="180" alt="桌宠顶部小锁（示例）">

![Unified desktop and sound settings](docs/demo/unified-settings.png)

## Follow client exit

Under **设置 → 连接 DeepSeek**, startup and shutdown follow are separate options. **随 DeepSeek 完全退出而关闭** is enabled by default: the pet closes about 8–10 seconds after the last client instance fully exits. A client still running in the tray keeps the pet open. Brief restarts are tolerated; launching the pet before the client does not immediately close it.

![连接与退出联动](docs/demo/connection-settings.png)

## Checking for updates and keeping your settings

Current version: **v0.5.2**. After each launch, the pet checks for a stable release and prompts you when a newer one is available. Right-click → **设置 → 版本与更新 → 立即检查更新** (Check for updates) to check manually.

Open **设置 → 版本与更新** (Settings → Version & Updates) to disable startup checks, check immediately, or restore ignored version reminders. A new-version prompt lets you open the release page, back up settings and media, remind you later, or ignore that version. A failed background check does not interrupt the pet.

Choose **自动选择** (automatic), **GitHub 官方源** (direct), or **镜像加速（中国大陆网络）** (mirror) under Version & Updates. Automatic mode tries GitHub first and falls back when it cannot connect. A fixed choice never silently switches. The update window shows the route and offers download links for the complete package, program patch and checksums.

The third-party [GH-Proxy](https://gh-proxy.com/docs/github-accelerator) mirror handles only public release metadata and downloads; it may lag behind GitHub. Source and exit preferences travel with exported settings.

![Version and update settings](docs/demo/update-settings.png)

**Updates are downloaded and installed manually.** Choose the package for your installed version:

| Your installation | How to update |
| --- | --- |
| v0.5.1 | Download the [v0.5.2 program patch](https://github.com/Doya16/shorekeeper-deepseek-pet/releases/download/v0.5.2/Shorekeeper-DeepSeek-Settings-Patch-v0.5.2.zip), exit the pet, extract over its existing folder, and restart |
| New installation or another older version | Extract the [v0.5.2 full package](https://github.com/Doya16/shorekeeper-deepseek-pet/releases/download/v0.5.2/Shorekeeper-DeepSeek-Windows-v0.5.2.zip) into a new folder, then import your exported settings and assets ZIP if you have one |

The program patch preserves **GIFs / images, audio, bubble captions, fonts, and personal settings**. Before updating, use **保存与迁移 → 导出配置与素材包（ZIP）** (Save & Migrate → Export Settings & Assets ZIP) to keep a backup. Extract program patches into the application folder; do not import them as settings.

## Features

- **Task expressions:** separate GIFs for thinking, reading, editing, running tools, waiting for you, completion, errors, and pauses. Concurrent completions are queued individually.
- **Voices and captions:** add several clips to one action, pair each with its own text, and play a randomly selected pair. Automatic GIF changes allow the current voice to finish. Thinking speech defaults to once per turn; idle speech can play on every entry, once per launch, or occasionally.
- **Custom animations:** choose a bundled GIF or add your own image; adjust speed, looping, single playback, hold time, and the next state.
- **Resizing:** use Ctrl + mouse wheel to scale the pet. Drag the edges of bubbles and the balance badge, or preview their sizes in settings. Their saved proportions scale with the pet.
- **Mouse interactions:** configure separate GIFs, voices, and bubbles for head pats, double-clicking, dragging, dropping, hovering, and feeding.
- **Account balance:** show the combined purchased and bonus balance below the pet. Right-click to refresh or hover for currency and details. `*` indicates cached data; `--` means no data is available.
- **Launch with Harness:** enable the option in the DeepSeek connection tab. Click the tray icon to show or hide the pet.
- **Update reminders:** startup and manual checks, with remind-later and ignore-version options.
- **Audio and tray labels:** Windows Volume Mixer lists **守岸人 · DeepSeek** for separate volume control. The tray tooltip also identifies the DeepSeek edition.
- **Save and migrate:** changes save automatically; export settings and media or a complete portable application.

| Voice playback frequency | Connection and startup |
| --- | --- |
| ![Automatic voice frequency](docs/demo/voice-frequency.png) | ![Connection and startup settings](docs/demo/startup-setting.png) |

## Customization

Right-click the pet → **设置 → 交互工作室** (Interaction Studio). Select an action, then adjust its expression, bubble, and voice.

| What to change | Where to find it |
| --- | --- |
| GIF or image for each action | **GIF 素材** (GIF assets) → choose a thumbnail |
| Add your own assets | Import images, or open the asset folder, add files, and refresh |
| Looping, speed, hold time, next state | **播放与切换** (Playback & Transitions) |
| Multiple voices, each with its own caption | **语音与配对气泡** (Voices & Paired Bubbles) → add files → select one to edit |
| Show only the selected voice's caption | **气泡与字体 → 气泡内容 → 自定义音频+字幕** (Bubbles & Fonts → Bubble Content → Custom Audio + Subtitles) |
| Bubble width and balance badge size | Right-click → **调整大小** (Resize), or drag their left/right edges |

| Custom expressions | Paired voices and captions |
| --- | --- |
| ![GIF library](docs/demo/gif-library-panel.png) | ![Voice clips paired with individual captions](docs/demo/voice-pairs-panel.png) |

Supported images: GIF, animated WebP, PNG, JPG/JPEG, and static WebP. Audio: WAV, MP3, OGG, FLAC, M4A, and AAC. Fonts: TTF, OTF, and TTC. Place a UTF-8 TXT file with the same base name beside an audio file to import its caption. The pet also works without added audio.

## Moving to another computer

![Export settings and media together](docs/social/portable-profile.jpg)

Right-click → **设置 → 保存与迁移 → 导出 Windows 便携完整包** (Settings → Save & Migrate → Export Complete Portable Windows Package).

Extract the package on the new computer, install and sign in to Harness, launch the pet, and install the connection plugin from its connection settings. Your GIFs, fonts, voices, captions, and settings travel with the package. Account credentials and chat history are not included.

You can also import a Codex-edition settings and assets package to reuse your expressions, audio, captions, fonts, and animation preferences. Configure the DeepSeek connection separately.

## Compatibility

- Connects to the official Harness desktop client; ordinary DeepSeek browser chats are outside this edition's scope.
- Tasks started after installing the plugin appear in the pet's conversation list with numbered DeepSeek labels.
- “Thinking” indicates a task stage. Bubble text comes from your configured lines and captions.
- The v0.1.0 integration was tested with Harness **0.2.0-rc.2**, including real tasks, waiting for input, resuming, cancellation, and concurrent completions. See [validation notes](docs/VALIDATION.md).

## Asset sources and acknowledgments

Expression assets come from the [Wuthering Waves emoji collection](https://emoji.wuwa.games/). Crowdfunding QQ group: **1079834905**.

Thank you to all the Shorekeeper fans who funded the expression packs used in this project. See [third-party credits](THIRD_PARTY.txt) for fonts, character voices, and other assets.

<details>
<summary>Run from source</summary>

Install Python 3.11+ and run these commands in the project directory:

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

</details>
