# 09-服务器运维

> ⚙️ 本文件由 `update_index.py` **自动生成**（扫描本目录里的文件）：新加条目只要把文件放进本目录，再跑一次 `python update_index.py` 就会自动出现。请勿手改。
> 分类总览见根目录 [`INDEX.md`](../INDEX.md)。

| 类型 | 条目 | 一句话 |
|---|---|---|
| 模块 | [Docker 容器运维.md](Docker 容器运维.md) | 看状态 → 看日志 → 进容器 → 重启；改动走挂载卷；删前确认备份 |
| 模块 | [Nginx 站点结构（前后端同目录）.md](Nginx 站点结构（前后端同目录）.md) | root 指向 backend/public；前端产物 cp 复制；别 rm -rf 误删 index.php；别擅改 root |
| 模块 | [SSH 服务器连接与管理.md](SSH 服务器连接与管理.md) | 怎么连 → 密钥登录 → fail2ban 加固 → 日常管理 → 连不上怎么查 |
| 模块 | [TCP 死连接堆积排查与清理.md](TCP 死连接堆积排查与清理.md) | ESTAB 没有空闲超时，靠 timer/lastsnd 判死活；`ss -K` 必须带过滤条件，裸跑会连 SSH 一起杀 |
| 单条 | [conntrack 开机持久化.md](conntrack 开机持久化.md) | Debian 默认不保证开机加载模块，需 modules-load.d + 独立 sysctl service，且先 modprobe 再 sysctl -p |
| 单条 | [内核参数优先交发行版默认（实测异常才调）.md](内核参数优先交发行版默认（实测异常才调）.md) | 不预埋调优包，实测出问题才单点调并记录依据 |
| 单条 | [出站 25 端口被封怎么办.md](出站 25 端口被封怎么办.md) | 云厂商默认封出站 25，改走 587 中继，别指望解封 |
| 单条 | [小内存服务器优化.md](小内存服务器优化.md) | 用 zram 不用磁盘 swap，算法选 zstd，swappiness 调到 100 |
| 单条 | [换机或恢复服务器时参数必须按真机复核.md](换机或恢复服务器时参数必须按真机复核.md) | ZRAM/conntrack/journald 按当前真机内存重算，不照抄旧机器数值 |
| 单条 | [改生产配置前先备份并停服务.md](改生产配置前先备份并停服务.md) | 改前留备份，停服务 → 覆盖 → 起服务避免写入竞态 |
| 模块 | [日志与磁盘防撑满 （journald 限容、apt 自动清、旧内核清理）.md](日志与磁盘防撑满 （journald 限容、apt 自动清、旧内核清理）.md) | 小磁盘服务器防日志/缓存/旧内核慢慢撑满盘 |
| 模块 | [流量监控三件套 （vnstat、iftop、nethogs）.md](流量监控三件套 （vnstat、iftop、nethogs）.md) | 历史统计 + 实时按 IP + 实时按进程，先 vnstat 看历史再 iftop/nethogs 看实时 |
| 模块 | [证书申请与自动续期.md](证书申请与自动续期.md) | acme.sh：HTTP 验证 / DNS 验证 → 装到 Web 服务器 → 自动续期 → 排查 |

### 📁 vnstat 流量统计（vnstat_stat.py）/

| 类型 | 文件 | 一句话 |
|---|---|---|
| 附件 | [servers.json.示例](vnstat 流量统计（vnstat_stat.py）/servers.json.示例) | 脚本 / 模板（不计入条目数） |
| 模块 | [vnstat 服务器流量统计（vnstat_stat.py）.md](vnstat 流量统计（vnstat_stat.py）/vnstat 服务器流量统计（vnstat_stat.py）.md) | 一条命令把多台机器各自的 vnstat 汇总成小时/天报表（只读，含收发拆分与月储备建议）（一个工具一个文件夹：脚本 + 清单模板 + 用法参考都在文件夹里） |
| 附件 | [vnstat_stat.py](vnstat 流量统计（vnstat_stat.py）/vnstat_stat.py) | 脚本 / 模板（不计入条目数） |

## 备注（历史）

2026-09-12 新增 TCP 死连接堆积排查与清理（模块，含 ss 列序坑 + `ss -K` 裸跑自杀）；2026-09-29 新增换机复核、内核参数交默认两条；2026-10-06 **并入**多机流量汇总工具（一个工具一个文件夹 `vnstat 流量统计（vnstat_stat.py）/`：内含 `vnstat_stat.py` + `servers.json.示例` + 用法参考）（原拟新建顶层目录，按用户要求并入）。**已超 8 条**：流量类（三件套 + vnstat 脚本）与内存/日志类是可合并候选，待用户决定
