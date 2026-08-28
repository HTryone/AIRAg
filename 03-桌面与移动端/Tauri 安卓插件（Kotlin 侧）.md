# Tauri 安卓插件（Kotlin 侧）

**结论**：原生代码必须放在独立插件里，否则每次打包都会被重新生成的工程覆盖掉。另外 Kotlin 侧读参数、取返回值、传参格式各有各的坑，写错一个就调不通。

谁需要看这条：用 Tauri 写安卓原生能力的人。

---

## 一、为什么要独立建插件

**打包命令会重新生成原生工程目录。** 直接写在生成目录里的 Kotlin 代码，下次打包就被覆盖没了。

所以：新建一个独立的插件 crate，原生代码写在里面，通过构建配置挂进主工程。

（证据：2026-08-17 提交 6e9eca4）

---

## 二、从零怎么建

### 第 1 步：建插件 crate

`Cargo.toml` 里注意 —— **`links` 字段必须写在 `[package]` 段**：

```toml
[package]
name = "你的插件名"
links = "你的插件名"
```

写进 `[lib]` 段的后果：**权限清单不生成**，主工程引用时 panic。这个报错完全看不出是 `links` 写错了位置。

### 第 2 步：配 Gradle

插件的 `build.gradle.kts` 必须配两样：

- `jvmTarget`（Java 版本）
- 依赖 `:tauri-android`

漏任一个编译不过。（证据：2026-08-17 提交 6e9eca4）

### 第 3 步：Rust 侧注册

```rust
tauri::Builder::default()
    .plugin(tauri_plugin_xxx::init())
```

插件注册后，它的命令名带 `plugin:` 前缀。

### 第 4 步：忽略规则

插件目录里忽略 `target/` 和 `Cargo.lock`（生成物，不进 git）。

---

## 三、调用侧的四个坑

### 1. 读参数：只有 `getArgs()`

Tauri v2 的 `Invoke` **没有 `getString` 这类快捷方法**，只有 `getArgs()`：

```kotlin
val name = invoke.getArgs().getString("name")
```

直接写 `invoke.getString("name")` 编译不过。

### 2. 取返回值：按对象取，不能按字符串取

Kotlin 返回的是一个对象（JSObject）时，前端要按对象类型取字段：

```ts
const res = await invoke<{ uri: string }>("plugin:xxx|open")
const uri = res.uri
```

按字符串取（`invoke<string>()`）拿到的是错的。

### 3. 传参格式：两种命令不一样

| 命令类型 | 传参格式 |
|---|---|
| Rust 原生命令 | **数组** `invoke("命令名", [参数1, 参数2])` |
| 带 `plugin:` 前缀的 Kotlin 命令 | **对象** `invoke("plugin:xxx", { 名: 值 })` |

混用会报参数解析错误。

### 4. 方法名用驼峰

Kotlin 侧方法名必须 camelCase，与前端调用名对得上。

---

## 四、避坑表

| 坑 | 后果 | 正确做法 |
|---|---|---|
| 原生代码写在生成目录 | 下次打包被覆盖 | 建独立插件 crate |
| `links` 写 `[lib]` 段 | 权限清单不生成、主工程 panic | 写 `[package]` 段 |
| 用 `invoke.getString()` | 编译不过 | 用 `invoke.getArgs().getString()` |
| 返回值按字符串取 | 拿到的是错的 | 按对象类型取字段 |
| 两种命令传参格式混用 | 参数解析错误 | Rust 命令用数组，插件命令用对象 |
| Gradle 漏配 jvmTarget 或依赖 | 编译不过 | 两个都配上 |
| 改了原生代码覆盖安装 | 装的是旧壳，改动没生效 | 卸载重装 |

---

## 相关

- 权限怎么配：[Tauri 权限配置（capability、命令清单、远程域白名单）](Tauri%20权限配置（capability、命令清单、远程域白名单）.md)
- 落盘命令怎么实现：[安卓文件落盘（MediaStore、SAF、文件描述符）](安卓文件落盘（MediaStore、SAF、文件描述符）.md)
- 后端怎么验：[Rust 与 Tauri 后端改动怎么验证](Rust%20与%20Tauri%20后端改动怎么验证.md)
- 代码分层：[分层原则（视图层、业务层、原生层、胶水层）](../12-技术栈架构/分层原则（视图层、业务层、原生层、胶水层）.md)
