# Electron 客户端逆向

从桌面客户端里挖出内部 API 和凭据，让脚本能直接调。这是完整流程，单独看这一篇就够。

**流程**：找到 asar → 提取字符串 → 定位凭据文件 → 试接口 → 判定能不能脚本化。

---

## 一、asar 包在哪、能不能读

Electron 应用的代码打包在 `resources/app.asar`（安装目录下）。

**asar 是打包不是加密**，里面的 JS 是明文，直接用 Python 读就行，不需要解包工具。

```python
p = r"C:\Users\xxx\AppData\Local\Programs\某应用\resources\app.asar"
d = open(p, "rb").read().decode("utf-8", "ignore")
```

---

## 二、提取字符串

**不要用 grep。** 压缩后的 JS 一行几万字符，grep 匹配到就直接输出：

```
[Omitted long matching line]
```

什么都看不到。用 Python 的 `find` + `repr()`：

```python
for kw in ["checkin", "Authorization", "getAuthSavePath"]:
    i = 0
    while True:
        i = d.find(kw, i)
        if i < 0:
            break
        print(kw, "->", repr(d[max(0, i-300):i+300]))
        i += 1
```

要点：
- `repr()` 把换行转义掉，输出仍是单行，不会被截
- 二进制读 + `errors="ignore"`，避免个别字节解码失败
- **关键词顺序**：先搜函数名（`getAuthSavePath`、`getBasePath`、`AuthenticationStorage`），再搜接口路径（`/v2/billing/`），最后搜协议字段（`Authorization`、`accessToken`）

函数名比接口路径更容易命中，因为路径常被拼接成片段。

---

## 三、定位凭据文件

在 asar 里搜这些关键词，读它附近的路径拼接逻辑：

```
getAuthSavePath
getBasePath
EXTENSION_DATA_DIR_NAME
sharedDataPath
AuthenticationStorage
```

然后按代码里的拼接顺序手动还原路径。

### 实例：WorkBuddy

```
getAuthSavePath()  →  path.join(sharedDataPath, "auth", `${authenticationId}.info`)
getBasePath()      →  <LOCALAPPDATA>/CodeBuddyExtension/Data/Public
```

拼出来：

```
%LOCALAPPDATA%\CodeBuddyExtension\Data\Public\auth\workbuddy-desktop.info
```

明文 JSON，字段：

| 字段 | 用途 |
|---|---|
| `auth.accessToken` | 接口鉴权 |
| `auth.refreshToken` | 续期（大概率用不了，见下） |
| `auth.domain` | 部分接口要放在 `X-Domain` 头 |
| `auth.expiresAt` | 到期时间戳，毫秒 |
| `auth.refreshExpiresAt` | 刷新令牌到期 |
| `account.uid` | 放 `X-User-Id` 头 |
| `account.nickname` | 日志显示用 |

### 三个注意点

1. **有些应用存在 `local_storage/*.info`，且是 gzip + base64 编码的**，要先解压再看
2. **拿到 refresh token 不等于能续期**。刷新需要 client_id 和 refresh endpoint，产品配置里经常不暴露。那就只能靠客户端重新登录来续期，脚本定期提醒用户重新导出
3. **多账号**：客户端切换登录通常用 `fs.renameSync` 覆盖同一路径，所以要给每个账号单独存一份快照文件。导出后随便切账号，已存的快照不受影响

---

## 四、试接口

拼好请求头发一次，**拿到 `code:0` 才算通**。

```python
headers = {
    "Accept": "application/json",
    "Content-Type": "application/json",
    "Authorization": "Bearer " + token,
    "X-User-Id": uid,
}
if domain:
    headers["X-Domain"] = domain
```

通用套路：
- 同时准备**多个端点**（主域名 + 备用域名），依次尝试取第一个成功的
- 超时 20 秒，太长会拖垮批处理
- 写操作（签到、领奖、下单）**先调查询接口确认状态再执行**，保证幂等

---

## 五、判定能不能脚本化

有些接口免签名，有些要签名 —— **同一服务里两种都有**。

### 实测案例

WorkBuddy 的积分查询接口 `/v2/billing/meter/get-user-resource`：

```
2 个端点 × 3 组请求头（含 X-Product / X-Client-Type）→ 全部 403，code 10085「请求不合法」
```

而同一服务的签到接口 `/v2/billing/meter/daily-checkin` 免签名，脚本正常调用。

### 止损线

试到这个程度就停：

1. 换端点（主域名 + 备用域名）
2. 换请求头组合，2-3 组，把从 asar 里找到的疑似自定义头都加上
3. 换 body 参数

还是 403 + "请求不合法" → **判定需要额外签名，放弃脚本化**，改为读客户端界面或让用户提供数据。

不要继续试第 4、5、6 组。这是盲目迭代，见 [改之前先拿证据](../07-排错方法论/改之前先拿证据.md)。

签名逻辑通常在客户端 JS 里（搜 `sign`、`hmac`、`signature`），但即使找到了，也往往依赖客户端内部状态（时间戳 + 随机数 + 设备指纹），脚本复现成本极高，一般不值得。

---

## 六、避坑

| 坑 | 后果 | 正确做法 |
|---|---|---|
| 用 grep 搜 asar | 输出被截成 `[Omitted long matching line]` | Python `find` + `repr()` |
| 一次读整个 asar 到内存再正则 | 大文件慢且难定位 | 按关键词 `find` 逐个看上下文 |
| 以为有 refresh token 就能续期 | 续期失败，脚本以为能长期跑 | 先确认 refresh endpoint 和 client_id 是否暴露 |
| 只存一份凭据 | 切换账号后凭据被覆盖 | 每个账号单独导出一份快照 |
| 接口 403 继续换参数试 | 浪费时间，拿不到新信息 | 按止损线判定，改走客户端界面 |
| 找到接口就直接定时跑 | 重复执行出问题 | 写操作先查状态，保证幂等 |
