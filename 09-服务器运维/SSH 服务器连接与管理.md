# SSH 服务器连接与管理

从连上一台 Linux 服务器，到把它加固到能长期放着不管。单独看这一篇就够。

用户环境实测：面板机 `102.134.50.180`（root + 密码登录），Ak云 HK-02 `23.91.96.39`（内存 899MB）。

---

## 一、这是什么

远程登录 Linux 服务器并执行命令的通道。所有服务器运维都建立在能连上的前提上。

两个概念别混：

| 词 | 指什么 |
|---|---|
| `ssh`（小写） | 客户端命令，你在本机敲的 |
| `sshd`（带 d） | 服务端守护进程，跑在服务器上 |

重启服务时用的是 **sshd**，不是 ssh。

---

## 二、怎么连

### 密码登录（最省事，安全性最低）

```bash
ssh root@102.134.50.180
```

首次连接会问 `Are you sure you want to continue connecting`，输 `yes`（不是 `y`）。

### 密钥登录（推荐，配一次就一劳永逸）

**第 1 步：本机生成密钥**

```bash
ssh-keygen -t ed25519 -C "htryone@163.com"
```

一路回车。生成 `~/.ssh/id_ed25519`（私钥，不外传）和 `~/.ssh/id_ed25519.pub`（公钥，传到服务器）。

**第 2 步：公钥传到服务器**

```bash
ssh-copy-id root@102.134.50.180
```

输一次密码就传好了。Windows 的 Git Bash 自带这个命令。

没有 `ssh-copy-id` 时手动传：

```bash
cat ~/.ssh/id_ed25519.pub | ssh root@102.134.50.180 "mkdir -p ~/.ssh && cat >> ~/.ssh/authorized_keys"
```

**第 3 步：验证**

新开一个窗口：

```bash
ssh root@102.134.50.180
```

不用输密码 = 成功。

### 给服务器起别名

`~/.ssh/config`（没有就新建）：

```
Host panel
    HostName 102.134.50.180
    User root
    Port 22
Host hk02
    HostName 23.91.96.39
    User root
    Port 22
```

之后 `ssh panel` 就能连。这个文件里的 `Host` 是别名，不是变量，换个窗口照样有效。

---

## 三、加固：挡住暴力破解

服务器放公网，SSH 端口每天会被扫几百次。两件事必做。

### 第 1 步：装 fail2ban

Ubuntu / Debian：

```bash
apt update && apt install -y fail2ban
```

CentOS / Rocky：

```bash
yum install -y epel-release && yum install -y fail2ban
```

### 第 2 步：写自己的配置

**不要改 `/etc/fail2ban/jail.conf`**，升级时会被覆盖。建一个 `jail.local` 覆盖它：

```bash
cat > /etc/fail2ban/jail.local <<'EOF'
[sshd]
enabled  = true
port     = ssh
filter   = sshd
logpath  = /var/log/auth.log
maxretry = 3
findtime = 600
bantime  = 86400
EOF
```

| 参数 | 含义 |
|---|---|
| `maxretry` | 允许失败几次 |
| `findtime` | 在多长时间窗口内累计（秒） |
| `bantime` | 封多久（秒），86400 = 一天 |

CentOS 系日志路径是 `/var/log/secure`，不是 `auth.log`。填错路径 = 规则永不触发，看着像装好了其实没生效。

### 第 3 步：启动并验证

```bash
systemctl enable --now fail2ban
fail2ban-client status sshd
```

看到 `Currently banned: N` 且 N 大于 0 = 真在拦。**看到数字才算生效**，只看 `active (running)` 不够。

用户环境实测：启用后封禁了大量 SSH 暴力破解 IP。

### 第 4 步（可选）：彻底关掉密码登录

确认密钥能连上之后才做，否则会把自己锁在门外：

```bash
sed -i 's/^#\?PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config
systemctl restart sshd
```

**改完不要断开当前连接**，新开一个窗口用密钥连一次，成功了再关旧窗口。

---

## 四、日常管理

```bash
fail2ban-client status sshd              # 看封了多少
fail2ban-client set sshd unbanip 1.2.3.4 # 解封某个 IP
fail2ban-client set sshd banip 1.2.3.4   # 手动封
grep "Failed password" /var/log/auth.log | tail -20   # 看攻击来源
```

传文件：

```bash
scp ./local.zip root@102.134.50.180:/root/
scp root@102.134.50.180:/root/remote.log ./downloaded.log
```

整目录加 `-r`。

---

## 五、连不上怎么查

按现象对号入座：

| 现象 | 原因 | 怎么办 |
|---|---|---|
| 卡住不动，最后超时 | 网络不通 / 防火墙挡了 / 服务器关机 | `ping` 通不通；去云厂商控制台看安全组有没有放行端口 |
| 立刻报 `Connection refused` | 端口没服务在听 | 服务器没开 sshd，或端口不是 22 |
| 报 `Permission denied (publickey)` | 密钥没传上去，或本地没加载 | 加 `-v` 看它尝试了哪几个密钥 |
| 报 `REMOTE HOST IDENTIFICATION HAS CHANGED` | 服务器重装过，指纹变了 | `ssh-keygen -R 102.134.50.180` 清掉旧记录再连 |
| 昨天能连今天不行 | 多半是自己被 fail2ban 封了 | 云厂商控制台的 VNC 登进去解封 |

排查万能招，加 `-v` 看协商过程（最详细用 `-vvv`）：

```bash
ssh -v root@102.134.50.180
```

看到 `Offering public key: ...` 后面跟 `Permission denied`，就是服务端不认这把钥匙。

---

## 六、常见坑

| 坑 | 后果 | 正确做法 |
|---|---|---|
| 直接改 `jail.conf` | 软件升级后配置被覆盖 | 改 `jail.local` |
| `logpath` 照抄 Ubuntu 的路径到 CentOS | 规则永不触发，形同虚设 | Ubuntu 用 `auth.log`，CentOS 用 `secure` |
| 没验证密钥就关密码登录 | 把自己锁在服务器外面 | 保持旧连接不关，新窗口验证成功再说 |
| 重启服务用 `systemctl restart ssh` | 报 `Unit ssh.service not found` | 服务端是 `sshd` |
| 以为装了 fail2ban 就安全了 | 没看 `banned` 数字，实际没生效 | 必须跑 `fail2ban-client status sshd` 看数字 |
| 只靠密码登录且端口 22 暴露公网 | 长期被扫，迟早被撞开 | 密钥登录 + fail2ban |
| 卡在 `yes/no` 那步只输 `y` | 连接中断 | 必须完整输 `yes` |

服务器上的**长期任务**别直接挂在 ssh 窗口里——窗口一断进程就死。用 `nohup cmd &` 或 `tmux`。
