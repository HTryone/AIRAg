# Tauri v2 构建打包

一条命令同时产出 Windows 安装包和 Android APK。这篇是从环境到产物的完整流程。

用户环境实测：ArkPulse 用 `toolbox/build-all.mjs` 同时输出 Windows NSIS 与 Android APK，目标架构 aarch64 / x86_64（仅 64 位），Android 用自签名 keystore。

---

## 一、这是什么

Tauri v2 用 Rust 写壳、系统 WebView 渲染界面，产物体积远小于 Electron。

| 产物 | 格式 | 用途 |
|---|---|---|
| Windows | NSIS 安装包（`.exe`）、MSI | 桌面分发 |
| Android | APK / AAB | 移动端 |

Tauri 也支持 iOS 和 macOS，但**构建必须在对应系统上做**：Windows 产物只能在 Windows 上打，iOS 产物只能在 macOS 上打，没有交叉编译。

---

## 二、环境在哪

### Windows 侧

| 依赖 | 作用 |
|---|---|
| Rust 工具链（rustup） | 编译 Rust 壳 |
| MSVC 生成工具 | Windows 链接器 |
| Node.js | 跑前端构建脚本 |

### Android 侧

用户环境的路径配置（已实测可用）：

```
SDK 根目录：D:/Apps/SDKS
NDK：       30.0.15729638
JDK：       jdk17
build-tools：35 / 36
```

三个环境变量必须设：

| 变量 | 值 |
|---|---|
| `ANDROID_HOME` | `D:\Apps\SDKS` |
| `ANDROID_SDK_ROOT` | `D:\Apps\SDKS` |
| `NDK_HOME` | `D:\Apps\SDKS\ndk\30.0.15729638` |

`NDK_HOME` 里的版本号要对得上实际装的 NDK 目录名，写错了报的错往往是「找不到编译器」这种看不出根因的信息。

一次性设好（Git Bash 里逐行执行）：

```bash
setx ANDROID_HOME "D:\Apps\SDKS"
setx ANDROID_SDK_ROOT "D:\Apps\SDKS"
setx NDK_HOME "D:\Apps\SDKS\ndk\30.0.15729638"
```

`setx` 设完**只对之后新开的窗口生效**，当前窗口还是旧值。设完关掉终端重开，再验证（PowerShell 里执行）：

```powershell
[Environment]::GetEnvironmentVariable("ANDROID_HOME", "User")
[Environment]::GetEnvironmentVariable("NDK_HOME", "User")
```

输出 `D:\Apps\SDKS` 和 `D:\Apps\SDKS\ndk\30.0.15729638` 就是设好了。输出为空说明没设上，重跑上面的 `setx` 并重开窗口。

---

## 三、从零做

### 第 1 步：装依赖

```bash
cargo install tauri-cli --version "^2"
```

### 第 2 步：初始化 Android 支持

在项目根目录执行一次：

```bash
npm run tauri android init
```

生成 `src-tauri/gen/android` 目录。这个目录是生成物，但包含 keystore 配置，别整个忽略掉。

### 第 3 步：生成签名密钥

Android 要求 APK 必须签名。自签名（个人使用/内部分发够用）：

```bash
keytool -genkey -v -keystore D:/Apps/SDKS/arkpulse.keystore \
  -alias arkpulse -keyalg RSA -keysize 2048 -validity 10000
```

**密码和 alias 立刻记下来**，忘了就只能重新签名，用户升级时会因签名不一致装不上。

### 第 4 步：配置签名

`src-tauri/tauri.conf.json`：

```json
{
  "bundle": {
    "targets": ["nsis", "apk"],
    "android": {
      "keystore": "D:/Apps/SDKS/arkpulse.keystore",
      "keystorePassword": "你的密码"
    }
  }
}
```

密码直接写进配置文件会被提交到 git。正式项目用环境变量占位：

```json
"keystorePassword": "$KEYSTORE_PASSWORD"
```

这里的 `$KEYSTORE_PASSWORD` 是 Tauri 规定的占位写法，不是让你手填密码。打包时 Tauri 会去读系统里名叫 `KEYSTORE_PASSWORD` 的环境变量，读不到就报错。

先在 Windows 里把这个环境变量设上（设完重开终端才生效）：

```bash
setx KEYSTORE_PASSWORD "你的keystore密码"
```

### 第 5 步：限制目标架构

只要 64 位（现代 Android 设备的实际情况），打包时指定：

```bash
npm run tauri android build -- --target aarch64 --target x86_64
```

不加参数会连 32 位一起打，产物变大、时间变长，而 32 位设备基本已淘汰。

---

## 四、一键构建

用户环境实测的脚本 `toolbox/build-all.mjs`，在项目根目录：

```bash
node toolbox/build-all.mjs
```

一次产出 Windows NSIS 和 Android APK。

用户明确提过的需求：**构建脚本应该跳过环境搜索步骤，直接执行打包**。每次都重新探测 SDK 位置会白白多花几十秒。做法是让脚本信任已配置好的 `ANDROID_HOME` / `NDK_HOME`，探测失败才回退到搜索。

---

## 五、打包纪律：先看进程再操作

**打包前先确认没有残留进程占着产物文件。**

Windows 上上一轮的 exe 还开着、或 Rust 编译进程没退干净，会导致写入失败，报错信息往往是「拒绝访问」这种看不出所以然的提示。

```powershell
Get-Process | Where-Object { $_.Name -like "*arkpulse*" -or $_.Name -like "*cargo*" }
```

有残留就先停：

```powershell
Stop-Process -Name arkpulse -Force
```

这条纪律是用户明确要求过的固有序次，每次打包前必做，不要等报错了才回头查进程。

---

## 六、排查

| 报错 | 原因 | 怎么办 |
|---|---|---|
| `Android SDK not found` | 环境变量没设或路径写错 | 检查 `ANDROID_HOME` 指向的目录里有没有 `platforms`、`build-tools` |
| `NDK not found` | `NDK_HOME` 版本号对不上目录名 | `ls D:/Apps/SDKS/ndk` 看实际目录名 |
| `Unsupported class file major version` | JDK 版本不匹配 | Android Gradle 插件要 JDK 17，不是 8 也不是 21 |
| `failed to find Build Tools` | build-tools 版本没装 | SDK Manager 装 35 或 36 |
| `Access is denied` 写产物失败 | 上一轮进程没退 | 按第五节停进程 |
| Rust 编译巨慢 | 首次编译要拉全部依赖 | 第一次慢是正常的，之后有缓存 |

看详细日志加 `--verbose`：

```bash
npm run tauri android build -- --verbose
```

---

## 七、常见坑

| 坑 | 后果 | 正确做法 |
|---|---|---|
| keystore 密码忘了 | 无法更新应用，用户得卸载重装 | 生成时立刻存档 |
| 每次打包都重新搜环境 | 白白多花几十秒 | 脚本直接信任已配好的环境变量 |
| 没停掉旧进程就打包 | 写入失败，报「拒绝访问」 | 打包前先看进程 |
| 默认打全部架构 | 产物臃肿、耗时长 | 只打 aarch64 + x86_64 |
| 想从 Windows 打 iOS 包 | 不可能 | iOS 必须在 macOS 上构建 |
| keystore 密码硬编码进配置文件 | 提交 git 泄露 | 用环境变量占位 |
| 整个 `gen/android` 加进 .gitignore | 签名配置丢失，换机器打不了 | 只忽略 `gen/android/app/build` 这类产物目录 |

---

## 相关

- 路径怎么写：[Git Bash 路径写法](Git%20Bash%20路径写法.md)
- 打包脚本本身：[bat 文件用 ASCII 内容](bat%20文件用%20ASCII%20内容.md)
