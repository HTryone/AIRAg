# WebDAV 直读openlist（绕过挂载盘读文件内容）

把网盘（如通过挂载工具映射的 WebDAV）当本地盘用很方便，但**用 Python 读取文件内容字节时会失败**——只能读到元数据，读不到正文。这篇讲怎么绕过挂载盘，直接走 WebDAV 的 HTTP 接口把字节拉到内存处理。

---

## 一、现象（什么时候用这篇）

通过挂载工具把 WebDAV 网盘映射成盘符（如 `Z:`）后：

- **能读**：`os.path.getsize`、文件名、修改时间等元数据
- **读不到**：文件内容字节

具体报错：

- `open(path,'rb').read()` / `shutil.copyfile` → `Bad file descriptor`
- `win32file.ReadFile` → `拒绝访问(5)`
- 原生 `cmd` 的 `copy` / `robocopy` 也失败或卡死

依赖读字节的库（如音频标签库读标签）同样拿不到数据。

## 二、根因

挂载层把"列目录 / 读属性"透传了，但"读文件内容"这条路径在 Windows 重定向文件系统里没打通（或权限 / 锁被卡）。这不是 Python 的锅——换 `cmd`、换 `robocopy` 一样失败。

**结论：不要跟挂载盘较劲，直接走 WebDAV 的 HTTP 接口。**

## 三、怎么做（直接走 HTTP）

用 `requests` 发 `PROPFIND` 列文件、`GET` 拉内容，全程在内存处理，不落盘。

### 第 1 步：先探测认证方式（prepare_auth）

很多 WebDAV 服务只认 **Digest** 认证（浏览器能进、程序进不去，就是因为浏览器自己协商了 Digest，而代码写死 Basic 一直 401）。

```python
import requests
from requests.auth import HTTPBasicAuth, HTTPDigestAuth

def webdav_prepare_auth(url, user, pwd):
    # 先发一个 Basic 探测，看服务端认不认、要不要 Digest
    r = requests.request("PROPFIND", url, auth=HTTPBasicAuth(user, pwd),
                         headers={"Depth": "0"}, timeout=10)
    if r.status_code == 401:
        auth_header = r.headers.get("WWW-Authenticate", "")
        if "digest" in auth_header.lower():
            return HTTPDigestAuth(user, pwd)      # 改成 Digest
    return HTTPBasicAuth(user, pwd)
```

### 第 2 步：列文件（webdav_list）

把上一步拿到的 `auth` 透传下去，**不得**在这里重新 `new` 一个 Basic auth——否则前面的协商白做，又变回 401。

```python
def webdav_list(url, auth):
    r = requests.request("PROPFIND", url, auth=auth,
                         headers={"Depth": "infinity"}, timeout=30)
    # 解析 XML 响应里的 <d:href> 和 <d:resourcetype>
    # 目录项是 <d:collection>，文件项才拉内容
    ...
```

路径前缀坑：有的服务 WebDAV 根不是 `/`（如某网盘服务真实路径是 `<域名>/dav` 无尾斜杠）。填错会返回 405，可捕获 405 后把 URL 第一段换成正确前缀重试。

### 第 3 步：拉内容（webdav_get）

对每个文件 `GET`，字节进内存，直接算哈希 / 解析标签，**不落盘**。

```python
def webdav_get(file_url, auth):
    r = requests.get(file_url, auth=auth, timeout=60)
    data = r.content                       # 全部字节已在内存
    import hashlib
    h = hashlib.sha256(data).hexdigest()   # 算哈希
    # 解析标签：把 bytes 包成类文件对象喂给库
    # from io import BytesIO
    # meta = read_meta_fo(BytesIO(data))
    return h, data
```

大库注意：逐文件 `GET` 会**下载全部字节**，流量和耗时都大。只在识别重复 / 提取标签时用，且体量要心里有数。

### 第 4 步：删除（webdav_delete）

远端没有回收站，删除即永久。先明确警告用户。

```python
def webdav_delete(file_url, auth):
    r = requests.request("DELETE", file_url, auth=auth, timeout=30)
    if r.status_code in (200, 204, 404):   # 404 当作已删
        return True
    return False
```

## 四、认证协商的致命陷阱

**Digest/Basic 协商结果只能由 `webdav_prepare_auth` 产出一次，并贯穿 list / get / delete 全程。** 任何下游函数都不得再 `HTTPBasicAuth(user, pwd)` 新建一个——曾因 list 忽略 prepare 的探测结果、自己写死 Basic，导致只认 Digest 的服务端一直 401（浏览器能进、程序进不去）。

## 五、排查

| 现象 | 原因 | 处理 |
|---|---|---|
| 401 但浏览器能进 | 代码写死 Basic，服务端只认 Digest | 走 prepare_auth 协商，下游透传 auth |
| 405 | URL 路径前缀错（根不是 `/`） | 捕获 405，把第一段换成正确前缀重试 |
| 列出来文件数比实际少 | 把目录项当文件拉了 / 漏了深层 | PROPFIND 用 `Depth: infinity`，跳过 `<d:collection>` |
| 重复扫描计数波动 | 可能是服务端云盘索引最终一致性，不是你的 bug | 交叉验证：拿原始 PROPFIND 总响应数 − 目录数，和你的结果对比；两次连续扫描一致则问题在上游 |

## 六、避坑表

| 坑 | 后果 | 正确做法 |
|---|---|---|
| 跟挂载盘较劲读字节 | open / copy / robocopy 全失败 | 直接走 HTTP PROPFIND / GET |
| 下游函数重建 Basic auth | 只认 Digest 的服务一直 401 | auth 只由 prepare 产出并透传 |
| GET 全量字节不计数 | 流量 / 耗时爆掉 | 只在必要时用，体量心里有数 |
| 远端删除不警告 | 误删无回收站 | 删前明确提示永久删除 |
| 路径前缀写死 `/` | 405 | 按服务实际根路径填，或 405 后修正 |

## 相关

- HTTP 容错思路：[多端点容错](多端点容错.md)
- 凭据别写死在脚本：[凭据存放与不进 git](../10-凭据与安全/凭据存放与不进%20git.md)
