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

## 五、版本单点

**版本号只在一处写，由构建脚本推算并同步到各处。禁止手动逐个改。**

需要同步的地方至少有：

| 文件 | 字段 |
|---|---|
| 壳的主配置文件 | version |
| `package.json` | version |
| Rust 主工程 `Cargo.toml` | version |
| 插件 `Cargo.toml` | version |
| `Cargo.lock` | 版本号 |
| 安卓工程 | versionCode |

漏改一处就会打出版本不一致的包。做法：构建脚本接受一个版本参数，其余全部由脚本写入。

```bash
node toolbox/build-all.mjs --version 1.2.3
```

---

## 六、壳层资源与启动页

壳层资源（启动图、启动页）的处理有三条，全踩过：

### 启动页不能用 `data:` 开头的地址

移动端的 WebView 初始化时会把页面地址当网址去解析，解析失败**直接闪退**。而且 `data:` 页面的来源是 opaque origin，里面发请求会坏。

**做法**：改用自定义协议提供启动页。

（证据：2026-08-17 提交 5e9ef9c）

### 壳层资源必须显式声明才打进包

app 窗口全部由原生代码创建时，**打包默认不会把前端产物和资源打进去**。本地资源必须显式写进打包资源清单。

**验证方法**：打完包，**解开 APK 看一眼资源文件确实在里面**再交付。不看等于没验。

（证据：2026-08-16 提交 8ff05a9）

### 改图标要改源头

改生成目录里的图标 PNG **没用**，每次打包都从源头 `icons/icon.png` 重建覆盖。

（证据：2026-08-16 提交 b82e7a3）

---

## 七、新路线并行上线

要替换一条正在跑、又不敢动的核心路径时，按这个来：

| 步骤 | 做法 |
|---|---|
| 1. 新路线完全独立 | 新增原生命令、新增前端实现，**全是新文件** |
| 2. 老路线一行不改 | 现有实现和其余链路一律不动 |
| 3. 工厂按开关选实现 | 初始化时判断开关，选新工厂还是老工厂 |
| 4. **开关语义用"禁用"** | 设了禁用值才退回老路，**默认走新路线** |
| 5. 新旧体验对齐 | 对用户的表现完全一致 |

**为什么开关用"禁用"而不是"启用"**：

- 默认走新路线，新代码才真的被跑到、真的被验证。用"启用"语义，新代码会长期没人用，等真切换时才发现是坏的
- 线上出问题，改一个值就退回老路，不用发版、不用改代码
- 新旧对外表现一致，否则差异会污染问题定位

**红线**：新路线只能新增，不得并入现有老路线。

实例见 [安卓文件落盘（MediaStore、SAF、文件描述符）](../03-桌面与移动端/安卓文件落盘（MediaStore、SAF、文件描述符）.md)。

---

## 八、打包纪律：先看进程再操作

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

## 九、排查

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

## 十、常见坑

| 坑 | 后果 | 正确做法 |
|---|---|---|
| keystore 密码忘了 | 无法更新应用，用户得卸载重装 | 生成时立刻存档 |
| 每次打包都重新搜环境 | 白白多花几十秒 | 脚本直接信任已配好的环境变量 |
| 没停掉旧进程就打包 | 写入失败，报「拒绝访问」 | 打包前先看进程 |
| 默认打全部架构 | 产物臃肿、耗时长 | 只打 aarch64 + x86_64 |
| 想从 Windows 打 iOS 包 | 不可能 | iOS 必须在 macOS 上构建 |
| keystore 密码硬编码进配置文件 | 提交 git 泄露 | 用环境变量占位 |
| 依赖手动开开发者命令提示符 | 换个人跑就扑空 | 脚本里用 `vswhere` 自动定位并注入工具链 |
| 依赖手动设一堆环境变量 | 同样扑空，且报错看不出根因 | 脚本自动探测，探测失败才回退搜索 |
| 安卓构建下载构建工具超时 | 卡住不动 | 走代理；Java 系工具不读 `https_proxy`，要用 `GRADLE_OPTS` 单独传 |
| 版本号手动逐个改 | 打出版本不一致的包 | 版本单点，脚本同步 |
| 整个 `gen/android` 加进 .gitignore | 签名配置丢失，换机器打不了 | 只忽略 `gen/android/app/build` 这类产物目录 |

---

## 相关

- 路径怎么写：[Git Bash 路径写法](Git%20Bash%20路径写法.md)
- 打包脚本本身：[bat 文件用 ASCII 内容](bat%20文件用%20ASCII%20内容.md)
