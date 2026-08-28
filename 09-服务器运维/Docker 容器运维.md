# Docker 容器运维

用容器跑的服务（Web、数据库、面板），日常运维靠 docker 命令，不是直接登机器改文件。单独看这篇够用。

---

## 一、这是什么

把服务打包成容器运行：一个应用常由多个容器组成（如 Web + 数据库）。运维对象不是"机器上的进程"，而是"容器"。

常用命令先认全：

| 命令 | 作用 |
|---|---|
| `docker ps -a` | 看所有容器状态（running / exited） |
| `docker logs -f <容器名>` | 实时看日志 |
| `docker exec -it <容器名> sh` | 进容器里排查 |
| `docker restart <容器名>` | 重启单个容器 |
| `docker compose restart <服务>` | 用 compose 时重启某个服务 |
| `docker stats` | 看容器实时资源占用 |

---

## 二、排查套路

1. `docker ps -a` 看容器是不是 running。
2. 不 running 或异常 → `docker logs <容器名>` 看报错。
3. 日志指向配置问题 → `docker exec -it <容器名> sh` 进容器看配置文件。
4. 确认问题后重启或改配置。

进容器后改动要注意：只改"挂了卷"的文件才会持久化，直接改容器内部文件系统，重启/重建就丢失。

---

## 三、日常管理

```bash
docker images                          # 看本地镜像
docker compose pull && docker compose up -d   # 拉新镜像并重建（compose 场景）
docker system prune -f                 # 清掉没用的悬空镜像/容器（谨慎，会删未用的）
```

更新前确认有数据备份（尤其是数据库容器）：

```bash
docker exec <db容器> <备份命令>         # 如 mysqldump / sqlite 复制
```

---

## 四、常见坑

| 坑 | 后果 | 正确做法 |
|---|---|---|
| 在容器里改了配置没挂卷 | 重启后改动全丢 | 配置走挂载卷，或写进镜像/compose |
| 直接 `docker rm` 有状态容器 | 没挂卷就数据全没 | 删前确认卷在，或先备份 |
| 重启不按顺序 | DB 没起 Web 就连不上 | 先起依赖（DB），再起应用 |
| 用 `systemctl restart` 去管容器服务 | 容器由 docker 管，systemctl 不一定生效 | 用 `docker restart` / `compose restart` |
| 改生产容器配置不备份 | 改崩了回不去 | 改前留一份当前态 |

---

## 五、相关

- 连服务器：[SSH 服务器连接与管理](SSH 服务器连接与管理.md)
- 改生产配置纪律：[改生产配置前先备份并停服务](改生产配置前先备份并停服务.md)
