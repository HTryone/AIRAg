# 流量监控三件套（vnstat、iftop、nethogs）

**结论**：服务器流量排查用三件套覆盖两个维度——历史统计（vnstat）和实时监控（iftop 按 IP、nethogs 按进程）。三者互补：先 vnstat 看历史趋势，再 iftop / nethogs 看实时是谁在跑。

---

## 一、这是什么

| 工具 | 维度 | 回答什么 |
|---|---|---|
| **vnstat** | 历史（自动入库） | 过去几小时 / 天 / 月跑了多少流量 |
| **iftop** | 实时（按 IP 对） | 现在谁在跑、哪个 IP 在占带宽 |
| **nethogs** | 实时（按进程） | 现在哪个进程在吃流量、PID 是多少 |

---

## 二、在哪 / 适用

三件套都是 Linux 命令行工具，服务器侧排查带宽异常、定位流量来源、确认是不是被刷流量时必装。

---

## 三、从零安装

```bash
apt-get update && apt-get install -y vnstat iftop nethogs
systemctl enable --now vnstat
```

注：vnstat 安装后约 5 分钟才积累出数据。iftop / nethogs 需要 root 权限。

---

## 四、日常管理（常用命令）

> 网卡名不一定是 `eth0`，先用 `ip -br addr` 查你机器实际的网卡名（常见 `eth0` / `ens3`），下面统一用 `<网卡>` 占位。

### vnstat — 历史

```bash
vnstat -d        # 今日 + 昨日对比
vnstat -h        # 按小时（看哪个小时飙了）
vnstat -m        # 按月
vnstat -tr 30    # 最近 30 秒平均速率
```

列含义：`rx` = 接收（下载），`tx` = 发送（上传）。

### iftop — 实时按 IP

```bash
iftop -i <网卡> -nP            # 不解析域名 + 显示端口（交互）
iftop -t -s 5 -i <网卡>        # 非交互：抓 5 秒快照（SSH 远程用）
iftop -i <网卡> -f "port 443"  # 只看 HTTPS
```

交互快捷键：`n` 切域名解析、`s`/`d` 切源 / 目的端口、`t` 切显示模式、`q` 退出。

### nethogs — 实时按进程

```bash
nethogs <网卡>                  # 交互
nethogs -t -c 3 -d 2 <网卡>     # 非交互：每 2 秒、共 3 次（SSH 远程用）
```

交互快捷键：`m` 切单位、`r` 按接收排序、`s` 按发送排序、`q` 退出。

---

## 五、排查套路

| 想弄清 | 命令 |
|---|---|
| 哪个小时流量大 | `vnstat -h` |
| 今天 / 本月总量 | `vnstat -d` / `vnstat -m` |
| 现在哪个 IP 在跑 | `iftop -i <网卡> -nP` |
| 现在哪个进程在吃 | `nethogs <网卡>` |
| 脚本里抓快照 | `iftop -t -s 5 -i <网卡>` / `nethogs -t -c 3 -d 2 <网卡>` |

组合流程：

```
1. vnstat -h              → 历史：哪个时段带宽飙了
2. iftop -i <网卡> -nP    → 实时：哪个 IP 在跑
3. nethogs <网卡>         → 进程：确认是哪个程序
```

SSH 远程抓快照（避免交互界面卡住断线）：

```bash
timeout 10 iftop -t -s 5 -i <网卡> -nP
timeout 10 nethogs -t -c 3 -d 2 <网卡>
```

---

## 六、避坑表

| 坑 | 后果 | 正确做法 |
|---|---|---|
| 网卡名写死 `eth0` | 机器上是 `ens3` 就全错 | 先 `ip -br addr` 查实际网卡名 |
| iftop / nethogs 交互模式跑在 SSH 里 | 界面卡住、断线丢失 | 加 `-t` 非交互 + `timeout` 包一层 |
| vnstat 刚装就查 | 没数据还以为坏了 | 等 5 分钟再查 |
| 只看实时不看历史 | 不知道是突发还是常态 | 先 `vnstat -h` 看趋势 |
| 过滤器写具体业务端口 | 换机器端口变了就失效 | 用 `<你的端口>` 占位，自己填 |

---

## 相关

- [小内存服务器优化](小内存服务器优化.md)
- [日志与磁盘防撑满（journald 限容、apt 自动清、旧内核清理）](日志与磁盘防撑满%20（journald%20限容、apt%20自动清、旧内核清理）.md)
