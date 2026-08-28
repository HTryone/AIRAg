# Electron 客户端试用数据清哪几个目录

**结论**：重置 Electron 客户端试用 / 激活状态，除了清注册表，还必须删 Chrome 存储目录 `Local Storage` / `DIPS` / `Session Storage`，否则试用倒计时照常跑。

## 为什么

Electron 基于 Chromium，把试用起始日、设备指纹等持久化在 userData 下的 Chrome 存储里，不只注册表。实测：只清注册表键后，客户端仍按 Local Storage 里的起始日倒计时。

## 怎么做

定位 app 的 userData 目录（一般在 `%APPDATA%\<应用名>\`，或安装目录 `resources/` 旁），删除这三个 **Chromium 标准目录**（所有 Electron 客户端同名，不随 App 变）：

- `Local Storage/`（LevelDB）
- `Session Storage/`
- `DIPS/`（Chromium 新版本的 Dedicated/Interest-group 存储数据库）

```bat
:: 示例路径，替换成你自己的 userData 位置
rmdir /s /q "%APPDATA%\<应用名>\Local Storage"
rmdir /s /q "%APPDATA%\<应用名>\Session Storage"
rmdir /s /q "%APPDATA%\<应用名>\DIPS"
```

同时清注册表对应键值。**注册表键名各 App 不同，没有通用清单**，不要套用别的 App 的键名。定位方法（任选其一）：

- 在 App 代码里搜注册表访问：`HKCU\\Software\\`、厂商名、`reg add` / `reg query` / `setValue`，跟出真实键名
- 直接清空该 App 在注册表下的整棵子树（如 `HKCU\Software\<厂商>\<应用名>`），最省事也最彻底

```bat
:: 清整棵子树（厂商/应用名替换成你查到的）
reg delete "HKCU\Software\<厂商>\<应用名>" /f
```

## 反例

只 `reg delete` 某个从别处抄来的键名 → 可能不是本 App 的键，重启客户端倒计时还在。
