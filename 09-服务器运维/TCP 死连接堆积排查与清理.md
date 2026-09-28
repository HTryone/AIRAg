# TCP 死连接堆积排查与清理

## 结论

**ESTAB 状态的连接没有「空闲超时」，内核不会自动回收。** 只要没人发 FIN 包，一条连接可以挂到天荒地老。看到几千条 ESTAB，不要先怀疑攻击，先查它们是不是「手机断网留下的尸体」。

## 为什么（三条清理路径，逐条排查）

一条 TCP 连接只有三种消失方式，任何一条没生效，连接就会堆积：

| 清理途径 | 触发条件 | 常见失效原因 |
|---|---|---|
| 对端发 FIN 正常关闭 | 客户端主动断开 | 手机切基站、锁屏、断电 → 一个包都不发，直接消失 |
| SO_KEEPALIVE 探测 | **应用必须显式 setsockopt** | 代理类程序（xray/v2ray 等）入站 socket 常不开，只有出站开 |
| conntrack 超时 | 防火墙开启并跟踪 | 防火墙关了就不跟踪（count=0）；且 conntrack 超时只丢表项，**不会关 socket** |

关键认知：**改内核的 `net.ipv4.tcp_keepalive_time` 对没开 SO_KEEPALIVE 的 socket 完全无效。** 很多人调了半天参数没反应，就是因为这条。

## 怎么查（取证步骤，按顺序）

### 1. 看总量和状态分布

```
ss -s
ss -tan | awk 'NR>1{print $1}' | sort | uniq -c | sort -rn
```

ESTAB 占绝大多数 → 是死连接堆积。TIME-WAIT 多 → 是短连接风暴，两回事。

### 2. 看归属哪个进程

```
ss -tanp state established | grep -o 'users:(("[a-z0-9.-]*"' | sort | uniq -c | sort -rn
```

### 3. 判死活（最关键一步）

```
ss -tan -o state established | head -20
```

看 `timer` 列：

- 有 `timer:(keepalive,...)` → 这个 socket 开了 SO_KEEPALIVE，内核在盯着，死了会自动收
- **无 timer** → 内核完全不管，挂一辈子

统计无 timer 的数量：

```
ss -tan -o state established | grep -c 'keepalive'
```

拿这个数和 ESTAB 总数对比，差值就是没人管的连接数。

### 4. 看空闲了多久

```
ss -tan -i state established | grep -oE 'lastsnd:[0-9]+'
```

`lastsnd` / `lastrcv` 单位是毫秒，是距上一次收发数据的时间。按分钟归类统计：

```
ss -tan -i state established | grep -oE 'lastsnd:[0-9]+' | sed 's/lastsnd://' | awk '{printf "%d\n", $1/60000}' | sort -n | uniq -c
```

超 12 小时没发过数据的，基本可以判定是死连接。

### 5. 看来源 IP 分布

```
ss -tan state established | tail -n +2 | awk '{print $3, $4}' | awk '{print $2}' | sed -E 's/\[?::ffff://; s/\]?$//; s/:[0-9]+$//' | sort | uniq -c | sort -rn | head -15
```

## ⚠️ 列序坑

`ss -tan state established`（带状态过滤时）**输出没有 State 列**，实际列序是：

| 位置 | 内容 |
|---|---|
| `$1` | Recv-Q |
| `$2` | Send-Q |
| `$3` | 本地地址:端口 |
| `$4` | 远端地址:端口 |
| `$5` | timer 或进程 |

不带 `state` 过滤时才是 `$1`=State。按 `$4` 当远端会整体错位一列，统计出来的「本地端口」其实是远端端口，方向判断直接反过来。

## 怎么清理

### 临时清理：ss -K

```
ss -K dst 1.2.3.4
ss -K 'dst 1.2.3.4 dport = :443'
```

### 根治：让应用开 SO_KEEPALIVE

代理类程序在入站配置里加 keepalive 参数（xray 系是 inbound 的 `sockopt.tcpKeepAliveIdle` / `tcpKeepAliveInterval`）。开了之后内核才会发探测包，死连接会在 `keepalive_time + intvl × probes` 后被清掉。

改之前确认：该程序版本是否支持这个字段；改完重启服务并等一个周期复查 `ss -tan -o` 里 timer 是否出现。

### 定期脚本（治标）

按 `lastsnd` 阈值筛出死连接，逐条 `ss -K` 精确杀。**必须带过滤条件**，且阈值要留足余量（建议 ≥2 小时），避免误杀正在长连接下载的用户。

## 反例（踩过的坑）

- **`ss -K` 不带任何过滤条件 = 关闭所有 TCP 连接，包括你自己的 SSH。** 实测执行后立刻 `Connection reset by peer`，SSH 会话被自己掐断。想验证 `ss -K` 语法请用 `ss -K --help` 或对单个无关 IP 试，绝不能裸跑。
- **指望 conntrack 帮你清 socket**：conntrack 的 `nf_conntrack_tcp_timeout_established` 只丢跟踪表项，不会发 RST 关 socket。防火墙关掉后 `nf_conntrack_count` 为 0，更谈不上了。
- **指望调 `tcp_keepalive_time`**：只对已开 SO_KEEPALIVE 的 socket 生效。实测 3120 条连接里只有 9 条有 timer，调这个参数对剩下 3111 条毫无作用。

## 实测参照（一台 1 核 473MB 的小鸡，跑代理服务）

| 指标 | 清理前 | 清理后 |
|---|---|---|
| 总连接数 | 3250 | 127 |
| ESTAB | 3120 | 7 |
| 进程 fd 数 | 3137 | 24 |
| 可用内存 | 136 MB | 161 MB |

清理后服务进程未重启、监听端口全在、负载无变化 —— 反证这几千条确实是毫无用处的死连接。

## 根治案例：升级代理程序本身

一台 xray 26.7.28 的服务器长期堆积 3120 条入站死连接（ESTAB 中仅 0.3% 带 keepalive timer）。升级到 **xray 26.9.9** 后，ESTAB 中带 keepalive timer 的比例升到 43%，连接数回落到个位数并稳定。

**排查同类问题时，第一步先看代理程序版本**，不要急着写清理脚本。官方 issue（如 Xray-core #5917）记录的入站回收缺陷，往往在新版本里已经悄悄修掉了。

判断有没有修好的**硬指标**是 `ss -tan -o` 里入站连接带不带 `timer:(keepalive...)`：

```
ss -tan -o state established | grep -c 'timer:(keepalive'
```

带 timer = 内核在盯着，死连接会被自动收；不带 = 内核完全不管，堆积只是时间问题。

注意区分"修好了"和"刚重启所以少"：进程重启后连接自然清零，要等至少一个堆积周期（原案例是 9 天）才能下结论，短期先看 timer 比例。

## 已证伪的路线（别再试第二次）

### 把 conntrack 的 established 超时调小

**实测无效。** 记录：某台跑代理的服务器上，防火墙开启、conntrack 正常工作、`nf_conntrack_count` 有值的情况下，ESTAB 死连接照样堆到 1088 条（单 IP 最高 633 条）。运维者当时把 `nf_conntrack_tcp_timeout_established` 从 3600 改到 300 测试，**没有解决问题，最后又改回 3600**。

原因：conntrack 超时到期只从哈希表删除表项（`nf_ct_delete`），**不会向 socket 发 RST**。对不经 NAT 的本机进程连接，删表项对 socket 毫无影响。

**调小反而有风险**：若连接被跟踪且空闲超过该值，后续包在 `-m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT` 规则下会被判成 NEW/INVALID 而丢弃 → **正常连接被切断**。这个值应该调大而不是调小。

### 指望 iptables/nftables 帮你关连接

防火墙只能决定包过不过，没有"关闭 socket"的能力。关掉一条 ESTAB 连接只有三种手段：应用自己 close、内核 keepalive 探测失败、`ss -K`（INET_DIAG_DESTROY）。防火墙一个都占不上。
