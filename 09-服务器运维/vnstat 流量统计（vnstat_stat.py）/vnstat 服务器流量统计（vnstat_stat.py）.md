# vnstat 服务器流量统计（vnstat_stat.py）

**结论**：一条命令把**多台服务器**各自的 vnstat 汇总成 Markdown 报表（逐小时 / 逐日 + 收发拆分 + 平均速率 + 月储备建议）。**全程只读**：只在远端跑 `vnstat --json` 和 `date`，不写远端任何文件、不改任何配置。

## 这是什么

- 数据源是**每台机器自己的 vnstat 数据库**（不是监控平台、不是云厂商控制台）。
- 一个脚本 + 一个 `servers.json` 清单：加机器 / 删机器只改清单。
- 输出是 Markdown 表格，可直接存档或贴进群里。
- 跨机对齐用 vnstat 记录自带的 **UTC 时间戳**，所以各机时区不同也不会错位。

## 在哪

`<知识库根>\09-服务器运维\`

```
vnstat_stat.py            主脚本（采集 + 出报表二合一）
servers.json.示例          清单模板（改名为 servers.json 后使用；含密码，勿提交 git）
```

> 具体项目的工作区里通常还有一份副本 + 该项目自己的机器清单（`servers.json` 里含真实密码，**不进本库**）。

## 依赖

```bash
python -c "import paramiko; print(paramiko.__version__)"   # 必须能 import，否则换带 paramiko 的解释器
bash --version                                             # Windows 用 Git Bash 执行 .py
```

**被采集的服务器**上要先有 vnstat：

```bash
apt-get install -y vnstat && systemctl enable --now vnstat     # Debian/Ubuntu
dnf install -y vnstat && systemctl enable --now vnstat         # RHEL 系
```

## 从零怎么做

### 1. 准备清单

把 `servers.json.示例` 改名为 `servers.json`（放在脚本同目录），按实际填写：

| 字段 | 说明 |
|---|---|
| `name` | 报表里显示的名字（建议按机器所在地区/用途取，简短） |
| `host` / `port` | IP 或域名 / SSH 端口 |
| `auth` | `key` 或 `password`（脚本按 `key_path` / `password` 是否存在决定用哪种） |
| `key_path` | 私钥路径；**推荐相对「工作区根」的相对路径**（脚本按脚本位置上三级解析），整个目录挪盘符都不用改 |
| `password` | 密码登录填密码；密钥登录可填 `null`，或填密码做兜底 |

> 清单文件缺失时脚本会**自动生成一份模板**，填好再跑即可。
>
> `servers.json.示例` 里**逐字段写了填法**（哪个字段填密钥、哪个填密码、哪些是尖括号占位符），先看它的 `_怎么用` / `_字段说明` / 两段示例再动手 —— 两种登录方式（密钥 / 密码）每台机器只填一种。
>
> 注意：脚本按「自己所在位置的上三级」当作"工作区根"来解析相对路径。**在 AIRAg 里直接跑时，这个"根"就是本库的上一级目录** —— 所以在本目录使用时，密钥建议写**绝对路径**，或改用自己工作区里的那份副本 + 自己工作区的清单。

### 2. 跑一次

```bash
cd <工具所在目录>
python vnstat_stat.py --hours 6
```

## 一键怎么做（常用命令）

```bash
# 最近 6 个完整小时 + 进行中小时（默认 --hours 6）
python vnstat_stat.py --hours 6

# 最近 N 个完整天：逐日 + 日均/最大单日 + 30 天推算 + 建议月储备（日均×30×1.5）
python vnstat_stat.py --days 7

# 同时把报表存成文件（不带值=按时间自动命名；给名字=存该名；给绝对路径=按路径存）
python vnstat_stat.py --hours 6 --out
python vnstat_stat.py --hours 6 --out 今晚.md
python vnstat_stat.py --days 7  --out "D:\<你的目录>\月度.md"
```

输出目录不存在会自动创建。`--days` 给了就按天出，忽略 `--hours`。

## 输出长什么样

小时报表固定三张表：**逐小时流量**（行=服务器，列=各小时）、**收/发拆分**（rx / tx / 合计 / 平均速率）、**进行中小时**（已过时长 / 已用流量 / 当前速率），末尾附各机采集时刻。表头带生成时间、统计窗口、服务器清单与口径说明，存成文件也不会认不出是哪一段。

> **表格格式不要改**：这是拿来存档和对比的固定视图，需要"更短的口头汇报"时在聊天里手工精简，**不要为了好看去改脚本输出**。

## 边界与参数

| 项 | 值 | 说明 |
|---|---|---|
| `--hours N` | N ≤ 96 | vnstat 小时粒度只保留 4 天 |
| `--days N` | N ≤ 62 | vnstat 日粒度只保留 62 天 |
| vnstat 默认保留期 | 5 分钟 48 小时 / 小时 4 天 / 日 62 天 / 月 25 个月 | 在**每台被采集机**的 `/etc/vnstat.conf` 调整 |
| 口径 | rx + tx 双向合计 | 商家若只按出站单向计费，储备数字减半 |
| 权限 | 只读 | 远端只执行 `vnstat --json` + `date` |

## 排查

| 症状 | 处理 |
|---|---|
| 某台显示 `FAIL` | 该机 SSH 不通或 vnstat 未装；报表其余部分照常输出，末尾列出失败原因 |
| `Not enough data available yet.` | 该机 vnstat 刚装，**需要攒够一个采样周期（约 5 分钟）才出数**，正常 |
| `ModuleNotFoundError: paramiko` | 用错解释器 → `python -c "import paramiko"` 确认，换带 paramiko 的那个 |
| 时间对不上 | 各机时区不同是正常的：脚本用 vnstat 的 UTC 时间戳对齐，小时标签取参考机本地时区 |
| 数字和商家面板对不上 | vnstat 是**双向合计**，且从安装时刻才开始记；面板可能按单向或按结算周期 |

## 避坑表

| 坑 | 事实（日期） | 做法 |
|---|---|---|
| 新机器刚接入，整张报表崩掉 | 2026-10-06 实测：某台机缺某个小时记录时，脚本用无默认值的 `next()` 取值，抛 `StopIteration → RuntimeError`，报表直接失败 | 已改为**缺该小时按 0 计**；新增机器后先跑一次确认 |
| 以为新机装完 vnstat 就立刻有数 | 2026-10-06 实测：`vnstat -i <网卡>` 显示 `Not enough data available yet.` | 等 5~10 分钟再取；报表里先显示 0 属正常 |
| 用错 Python 解释器 | 2026-10-06 记录：某个精简 Python 环境里没有 paramiko | 先 `python -c "import paramiko"` 验；文档串里别再写死某台机器的解释器路径 |
| 把真实清单提交进 git | — | `servers.json` 含密码，**只放工作区、不进库**（见 `../10-凭据与安全/凭据存放与不进 git.md`） |
| 想顺手改输出格式 | — | 报表是存档视图，**保持稳定**；要精简只在聊天汇报里精简 |

## 和其它条目的关系

- 要**实时**看"哪个 IP / 哪个进程在跑流量"（历史统计之外的场景）→ 见 `流量监控三件套（vnstat、iftop、nethogs）.md`（同目录）。
- 小内存机器上 vnstat 与 zram、journald 的取舍 → 见 `小内存服务器优化.md`（同目录）。
