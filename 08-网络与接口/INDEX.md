# 08-网络与接口

> ⚙️ 本文件由 `update_index.py` **自动生成**（扫描本目录里的文件）：新加条目只要把文件放进本目录，再跑一次 `python update_index.py` 就会自动出现。请勿手改。
> 分类总览见根目录 [`INDEX.md`](../INDEX.md)。

| 类型 | 条目 | 一句话 |
|---|---|---|
| 模块 | [Cloudflare 落点与跨境链路定位（CF-RAY、traceroute）.md](Cloudflare 落点与跨境链路定位（CF-RAY、traceroute）.md) | 五步定位 + 四条反模式；测落点必须加不走代理的参数 |
| 单条 | [JS 流式管道 Promise 链必须恒 fulfilled.md](JS 流式管道 Promise 链必须恒 fulfilled.md) | `catch` 里再抛出会让链永久失败，之后每个请求秒失败 |
| 模块 | [WebDAV 直读openlist（绕过挂载盘读文件内容）.md](WebDAV 直读openlist（绕过挂载盘读文件内容）.md) | 挂载盘读不到字节 → 走 HTTP PROPFIND/GET；Digest/Basic 只由 prepare 产出并透传 |
| 单条 | [WebSocket 长连接的超时与重连.md](WebSocket 长连接的超时与重连.md) | 等待必须有超时、重连不能走关闭流程、终态要显式守卫 |
| 单条 | [写操作接口要做幂等.md](写操作接口要做幂等.md) | 先查状态再执行 |
| 单条 | [多端点容错.md](多端点容错.md) | 依次尝试取第一个成功 |
| 模块 | [大文件传输调优.md](大文件传输调优.md) | 调参顺序（分片→并发→窗口→ack）、看振荡不看峰值、止损线 |
| 单条 | [接口探测要有止损线.md](接口探测要有止损线.md) | 两三组合失败就判定不可行 |

## 备注（历史）

正常，本次新增 WebDAV 直读openlist（绕过挂载盘读文件内容）（模块）
