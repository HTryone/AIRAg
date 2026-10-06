"""vnstat 服务器流量统计（全程只读）

用法（在任意窗口直接跑）：
  vnstat_stat.py --hours 6
  vnstat_stat.py --hours 4 --out report.md
  vnstat_stat.py --days 3

- 服务器清单与凭据读同目录 servers.json，改机器/加机器只改那个文件。
- 两种报表：--hours N 走小时报表（逐小时 + 收发拆分 + 进行中小时）；
  --days N 走天报表（逐日 + 日均 + 月储备建议），两者互斥，给了 --days 就按天出。
- --out 默认存到工作区临时目录（<工作区>/.workbuddy/.temp/），相对脚本位置解析，不固定盘符。
- servers.json 里的 key_path 用相对路径（相对工作区根，即本目录上三级）也可。
"""
import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import paramiko

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent.parent      # 工作区根（本目录 = 根/.workbuddy/tools/xxx）
TEMP_DIR = ROOT / ".workbuddy" / ".temp"  # 默认输出目录，随工作区走，不固定盘符
GIB = 1024 ** 3
MARK = "=====MARK====="

CMD = (
    "vnstat --json; echo '" + MARK + "'; "
    "date +%s; date '+%Y-%m-%d %H:%M:%S %z'; date -u +%s; "
    "cat /etc/timezone 2>/dev/null; vnstat --version | head -1; hostname"
)


def load_servers():
    cfg = HERE / "servers.json"
    if not cfg.exists():
        # 首次复用：自动生成模板，填好服务器信息后重跑
        template = {
            "_说明": "服务器清单与凭据。本文件含 SSH 密码，勿提交 git、勿外传。"
                     "key_path 可用相对工作区根的相对路径。",
            "servers": [
                {"name": "示例机", "host": "1.2.3.4", "port": 22, "auth": "password",
                 "key_path": None, "password": "把密码填这里"},
            ],
        }
        with open(cfg, "w", encoding="utf-8") as fh:
            json.dump(template, fh, ensure_ascii=False, indent=2)
        raise SystemExit(f"未找到 servers.json，已生成模板：{cfg}\n"
                         f"请填入服务器信息后重新运行。")
    with open(cfg, encoding="utf-8") as fh:
        data = json.load(fh)
    return data["servers"]


def collect(srv):
    cli = paramiko.SSHClient()
    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    kw = dict(
        hostname=srv["host"], port=int(srv.get("port", 22)), username="root", timeout=20,
        banner_timeout=30, auth_timeout=30, allow_agent=False, look_for_keys=False,
    )
    if srv.get("key_path"):
        kp = Path(srv["key_path"])
        if not kp.is_absolute():
            kp = ROOT / kp
        kw["key_filename"] = str(kp)
    if srv.get("password"):
        kw["password"] = srv["password"]
    try:
        cli.connect(**kw)
        _, stdout, stderr = cli.exec_command(CMD, timeout=90)
        out = stdout.read().decode("utf-8", "replace")
        err = stderr.read().decode("utf-8", "replace")
        rc = stdout.channel.recv_exit_status()
        cli.close()
        return {"ok": rc == 0 and "interfaces" in out, "stdout": out, "stderr": err,
                "host": srv["host"], "name": srv["name"]}
    except Exception as exc:  # noqa: BLE001
        try:
            cli.close()
        except Exception:  # noqa: BLE001
            pass
        return {"ok": False, "error": repr(exc), "host": srv["host"], "name": srv["name"]}


def gib(n):
    return n / GIB


def mbps(nbytes, seconds):
    return nbytes * 8 / seconds / 1e6


def bj_now(stdout):
    """参考机的采集时刻（UTC 秒）换算成北京时间，用于报表表头。"""
    meta = stdout.split(MARK, 1)[1].strip().splitlines()
    return datetime.fromtimestamp(int(meta[0]), timezone.utc) + timedelta(hours=8)


def build_report(raw, hours, order):
    data = {}
    failed = []
    for name in order:
        rec = raw.get(name)
        if not rec or not rec.get("ok"):
            failed.append(name)
            continue
        body, meta = rec["stdout"].split(MARK, 1)
        vn = json.loads(body)
        iface = vn["interfaces"][0]
        data[name] = {
            "hours": iface["traffic"]["hour"],
            "now_ts": int(meta.strip().splitlines()[0]),
            "iface": iface["name"],
        }
    if not data:
        return "所有服务器采集失败，无报表。", failed

    names = [n for n in order if n in data]
    ref = data[names[0]]["hours"]
    cur_ts = ref[-1]["timestamp"]
    complete = [h["timestamp"] for h in ref[-(hours + 1):-1]]
    def label_of(ts, with_year=False):
        """用参考机给该小时做标签；参考机缺该小时时退回 epoch，避免 StopIteration。"""
        h = next((x for x in ref if x["timestamp"] == ts), None)
        if h is None:
            return str(ts)
        if with_year:
            return (f"{h['date']['year']}-{h['date']['month']:02d}-{h['date']['day']:02d} "
                    f"{h['time']['hour']:02d}:00")
        return f"{h['date']['month']:02d}-{h['date']['day']:02d} {h['time']['hour']:02d}:00"

    labels = [label_of(ts) for ts in complete + [cur_ts]]

    def full_label(ts):
        return label_of(ts, with_year=True)

    lines = []
    add = lines.append
    add("# vnstat 服务器流量报表（按小时）\n")
    add(f"- 生成时间：{bj_now(raw[names[0]]['stdout']):%Y-%m-%d %H:%M:%S}（北京时间 UTC+8）")
    add(f"- 统计窗口：{full_label(complete[0])} ~ {full_label(cur_ts)}"
        f"（含前不含后，{hours} 个完整小时）；另有 {full_label(cur_ts)} 起进行中")
    add(f"- 服务器：{'、'.join(names)}（各机自带 vnstat，全程只读）")
    add("- 口径：rx+tx 双向合计；小时标签按参考机本地时间\n")
    add(f"## 逐小时流量（rx+tx，GiB）\n")
    hlabels = labels[:hours]
    add("| 服务器 | " + " | ".join(hlabels) + f" | 最近 {hours} 小时合计 | 平均速率 |")
    add("|" + "---|" * (len(hlabels) + 3))

    tot_complete = tot_rx = tot_tx = 0
    rows = {}
    for name in names:
        d = data[name]
        byts = {h["timestamp"]: h for h in d["hours"]}
        cells, s, r, t = [], 0, 0, 0
        for ts in complete:
            h = byts.get(ts)
            v = (h["rx"] + h["tx"]) if h else 0
            cells.append(f"{gib(v):.2f}")
            s += v
            if h:
                r += h["rx"]
                t += h["tx"]
        cur = byts.get(cur_ts)
        rows[name] = dict(
            s=s, r=r, t=t,
            cur=(cur["rx"] + cur["tx"]) if cur else 0,
            elapsed=d["now_ts"] - cur_ts,
        )
        tot_complete += s
        tot_rx += r
        tot_tx += t
        add(f"| {name} | " + " | ".join(cells) + f" | **{gib(s):.2f}** | {mbps(s, hours * 3600):.1f} Mbps |")

    def hour_bytes(n, ts):
        """某台机某小时的 rx+tx；该小时没有记录（新机刚接入监控 / 期间离线）按 0 计。"""
        for h in data[n]["hours"]:
            if h["timestamp"] == ts:
                return h["rx"] + h["tx"]
        return 0

    hour_tot = [sum(hour_bytes(n, ts) for n in names) for ts in complete]
    add(f"| **合计** | " + " | ".join(f"**{gib(v):.2f}**" for v in hour_tot)
        + f" | **{gib(tot_complete):.2f}** | {mbps(tot_complete, hours * 3600):.1f} Mbps |")

    add(f"\n## 收 / 发拆分（GiB）\n")
    add("| 服务器 | 下载 rx | 上传 tx | 合计 | 平均速率 |")
    add("|---|---|---|---|---|")
    for name in names:
        r = rows[name]
        add(f"| {name} | {gib(r['r']):.2f} | {gib(r['t']):.2f} | **{gib(r['s']):.2f}** | {mbps(r['s'], hours*3600):.1f} Mbps |")
    add(f"| **合计** | **{gib(tot_rx):.2f}** | **{gib(tot_tx):.2f}** | **{gib(tot_complete):.2f}** | "
        f"**{mbps(tot_complete, hours*3600):.1f} Mbps** |")

    add("\n## 进行中小时（截至采集时刻）\n")
    add("| 服务器 | 已过时长 | 已用流量 | 当前速率 |")
    add("|---|---|---|---|")
    tot_cur = 0
    for name in names:
        r = rows[name]
        tot_cur += r["cur"]
        add(f"| {name} | {r['elapsed']//60} 分 {r['elapsed']%60} 秒 | {gib(r['cur']):.2f} GiB | "
            f"{mbps(r['cur'], r['elapsed']):.1f} Mbps |")
    add(f"| **合计** | — | **{gib(tot_cur):.2f} GiB** | — |")

    add("\n采集时刻（各机本地）：")
    for name in names:
        rec = raw[name]
        meta = rec["stdout"].split(MARK, 1)[1].strip().splitlines()
        add(f"- {name} {rec['host']}：{meta[1]}（UTC {meta[2]}，iface {data[name]['iface']}）")

    if failed:
        add("\n⚠️ 采集失败（未纳入统计）：")
        for name in failed:
            err = raw.get(name, {}).get("error", "未知")
            add(f"- {name}（{raw.get(name, {}).get('host', '?')}）：{err}")
    return "\n".join(lines), failed


def build_day_report(raw, days_n, order):
    """按天报表：逐日用量 + 日均 + 月储备建议（含 50% 余量）。

    口径：vnstat 的 day 数组最后一条 = 今天（未过完），只展示不计入统计。
    日边界按各机本地时间；跨机同日标签可能有 12 小时错位，对长期日均影响很小。
    """
    data, failed = {}, []
    for name in order:
        rec = raw.get(name)
        if not rec or not rec.get("ok"):
            failed.append(name)
            continue
        body, meta = rec["stdout"].split(MARK, 1)
        vn = json.loads(body)
        iface = vn["interfaces"][0]
        entries = iface["traffic"]["day"]
        data[name] = {
            "complete": entries[:-1],          # 最后一条 = 今天（未过完）
            "partial": entries[-1] if entries else None,
            "iface": iface["name"],
        }
    if not data:
        return "所有服务器采集失败，无报表。", failed

    names = [n for n in order if n in data]

    def key(d):
        return (d["date"]["year"], d["date"]["month"], d["date"]["day"])

    axis = sorted({key(d) for n in names for d in data[n]["complete"]})[-days_n:]
    axis_set = set(axis)

    part = data[names[0]]["partial"]
    part_label = (f"{part['date']['year']}-{part['date']['month']:02d}-{part['date']['day']:02d}"
                  if part else "—")

    lines = []
    add = lines.append
    add("# vnstat 服务器流量报表（按天）\n")
    add(f"- 生成时间：{bj_now(raw[names[0]]['stdout']):%Y-%m-%d %H:%M:%S}（北京时间 UTC+8）")
    if axis:
        add(f"- 统计窗口：{axis[0][0]}-{axis[0][1]:02d}-{axis[0][2]:02d} ~ "
            f"{axis[-1][0]}-{axis[-1][1]:02d}-{axis[-1][2]:02d}（{len(axis)} 个完整天）；"
            f"另有 {part_label} 进行中")
    add(f"- 服务器：{'、'.join(names)}（各机自带 vnstat，全程只读）")
    add("- 口径：rx+tx 双向合计；日边界按各机本地时间（跨机同日可能有 12 小时错位）\n")
    add("## 逐日流量（rx+tx，GiB）\n")
    add("| 日期 | " + " | ".join(names) + " | 合计 |")
    add("|" + "---|" * (len(names) + 2))
    for k in axis:
        vals = []
        for n in names:
            e = next((d for d in data[n]["complete"] if key(d) == k), None)
            vals.append((e["rx"] + e["tx"]) if e else None)
        add(f"| {k[0]}-{k[1]:02d}-{k[2]:02d} | "
            + " | ".join("—" if v is None else f"{gib(v):.2f}" for v in vals)
            + f" | {gib(sum(v for v in vals if v is not None)):.2f} |")
    pv = [(p["rx"] + p["tx"]) if (p := data[n]["partial"]) else None for n in names]
    add("| 今天 ⏳ | " + " | ".join("—" if v is None else f"{gib(v):.2f}" for v in pv)
        + f" | {gib(sum(v for v in pv if v is not None)):.2f} |")

    add(f"\n## 日均与月储备建议（按上表 {len(axis)} 个完整天）\n")
    add("| 服务器 | 统计天数 | 日均 | 最大单日 | 30 天推算 | 建议月储备（30 天推算 +50%） |")
    add("|---|---|---|---|---|---|")
    tot_avg, few = 0.0, []
    for n in names:
        vals = [(d["rx"] + d["tx"]) / GIB for d in data[n]["complete"] if key(d) in axis_set]
        if len(data[n]["complete"]) < 3:
            few.append(n)
        if not vals:
            add(f"| {n} | 0 | — | — | — | — |")
            continue
        avg, mx = sum(vals) / len(vals), max(vals)
        tot_avg += avg
        add(f"| {n} | {len(vals)} | {avg:.2f} GiB | {mx:.2f} GiB | {avg * 30:.0f} GiB | "
            f"**{avg * 30 * 1.5:.0f} GiB/月** |")
    add(f"| **合计** | — | **{tot_avg:.2f} GiB/天** | — | **{tot_avg * 30:.0f} GiB** | "
        f"**{tot_avg * 30 * 1.5:.0f} GiB/月** |")

    add("\n采集时刻（各机本地）与数据源：")
    for n in names:
        meta = raw[n]["stdout"].split(MARK, 1)[1].strip().splitlines()
        add(f"- {n} {raw[n]['host']}：{meta[1]}（iface {data[n]['iface']}，日粒度保留 62 天）")
    add("\n口径提醒：vnstat 数是**双向合计**（rx+tx）；商家若只按出站单向计费，上面的储备数字减半即可。")
    if few:
        add(f"⚠️ 样本不足（完整天 < 3）：{'、'.join(few)} —— 日均仅供参考，攒够一周再校准更准。")
    if failed:
        add("\n⚠️ 采集失败（未纳入统计）：")
        for name in failed:
            err = raw.get(name, {}).get("error", "未知")
            add(f"- {name}（{raw.get(name, {}).get('host', '?')}）：{err}")
    return "\n".join(lines), failed


def main():
    ap = argparse.ArgumentParser(description="vnstat 服务器流量统计（只读）")
    ap.add_argument("--hours", type=int, default=6, help="小时报表：统计最近 N 个完整小时（默认 6）")
    ap.add_argument("--days", type=int, default=None,
                    help="天报表：统计最近 N 个完整天 + 月储备建议（给了它就忽略 --hours）")
    ap.add_argument("--out", nargs="?", const="", default=None,
                    help="报表存文件；不带值=自动命名存临时目录，带文件名=存临时目录，带完整路径=按路径存")
    args = ap.parse_args()

    servers = load_servers()
    order = [s["name"] for s in servers]
    raw = {}
    for srv in servers:
        rec = collect(srv)
        raw[srv["name"]] = rec
        state = "OK" if rec["ok"] else f"FAIL {rec.get('error', '')}"
        print(f"{srv['name']}: {state}", file=sys.stderr)

    if args.days is not None:
        report, failed = build_day_report(raw, args.days, order)
    else:
        report, failed = build_report(raw, args.hours, order)
    print(report)
    if args.out is not None:
        # 默认输出目录 = 工作区临时目录（相对脚本位置解析，不固定盘符）
        temp_dir = TEMP_DIR
        temp_dir.mkdir(parents=True, exist_ok=True)
        if args.out == "":
            from datetime import datetime
            fname = f"vnstat_report_{datetime.now():%Y%m%d_%H%M}.md"
        elif Path(args.out).is_absolute():
            fname = args.out
            temp_dir = None
        else:
            fname = args.out
        out_path = Path(fname) if temp_dir is None else temp_dir / fname
        out_path.parent.mkdir(parents=True, exist_ok=True)  # 目录不存在就自动创建
        with open(out_path, "w", encoding="utf-8") as fh:
            fh.write(report + "\n")
        print(f"\n报表已保存：{out_path}", file=sys.stderr)
    if failed:
        sys.exit(2)


if __name__ == "__main__":
    main()
