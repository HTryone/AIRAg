#!/usr/bin/env bash
# =============================================================================
# gh.sh —— 通用 GitHub 操作脚本（不绑定任何具体项目）
#
# 目的：让 agent 能安全地「提 issue / 提 PR / 回评论 / 贴标签 / 核实状态」，
#       而不是每次手拼带占位符的长命令。
#
# 授权铁律（重要）：
#   * 任何**写操作**（提 PR、提 issue、发评论、贴标签、关 issue）都要显式加 --yes，
#     并且 agent 在执行前必须先拿到用户的明确授权。
#   * 读操作（verify / pr-list / issue-list / issue-show / token-check）随时可用。
#   * 令牌只用 `git credential fill` 现取，**绝不落盘、绝不回显**。
#
# 用法（Git Bash）：
#   bash gh.sh help
#   bash gh.sh token-check
#   bash gh.sh repo-info                      # 当前目录 git 仓库的 owner/name
#   bash gh.sh verify [--dir <仓库目录>] [--repo owner/name] [--branch main]
#   bash gh.sh pr-list [--repo owner/name] [--state open|closed|all]
#   bash gh.sh pr-create "<标题>" <正文.md> [--repo owner/name] [--base main]
#                                            [--head <owner:branch>] [--dry-run] [--yes]
#   bash gh.sh issue-list [--repo owner/name] [--state open] [--limit 20]
#   bash gh.sh issue-show <编号> [--repo owner/name]
#   bash gh.sh issue-create "<标题>" <正文.md> [--repo owner/name] [--dry-run] [--yes]
#   bash gh.sh issue-comment <编号> <正文.md> [--repo owner/name] [--dry-run] [--yes]
#   bash gh.sh issue-label <编号> "bug,help wanted" [--repo ...] [--yes]
#   bash gh.sh issue-close <编号> [--repo ...] [--reason completed|not_planned] [--yes]
#   bash gh.sh api <GET|POST|PATCH> <path> [payload.json]     # 逃生口，只读用 GET
#
# 通用规则：
#   * 不写 --repo 时，用「当前目录（或 --dir）所在 git 仓库的 origin」推断 owner/name。
#   * PR 的 head 默认 = <你的登录名>:<当前分支>；跨仓库 PR 必须写 --head。
#   * 令牌需要 repo 权限（改 .github/workflows 里的文件还需 workflow 权限）。
#   * 若 api.github.com 直连不通：设 GH_PROXY（如 export GH_PROXY=socks5h://127.0.0.1:<你的代理端口>）。
#   * 凭据从哪来、有哪几个值要你自己填 → 见本文件内「★★★ 用之前先看这里 ★★★」配置区。
# =============================================================================
set -uo pipefail

# =============================================================================
# ★★★ 用之前先看这里：凭据从哪来、哪些值要你自己填 ★★★
#
# 【一、凭据：不要填在本文件里】
#   GitHub 令牌不由本文件保存，也不用环境变量传。脚本会问 git 凭据管理器要：
#
#       git config --global credential.helper manager   # 没配过先配（Windows 推荐）
#       bash gh.sh token-check                          # 验证现在能不能取到
#
#   第一次取用/推送时 git 会弹窗要求登录 GitHub，登录一次后令牌就存进凭据管理器了。
#   ⚠️ 令牌不要写进本文件、不要贴进命令行、不要提交进 git。
#      万一泄漏：立刻去 GitHub 设置里吊销并重新生成（处置办法见知识库 10-凭据与安全）。
#
# 【二、下面四个值按自己情况填，全是占位符，留空即表示"不预设"】
#   GH_PROXY_FALLBACK  代理地址。api.github.com 直连不通时才需要填。
#                      例：socks5h://127.0.0.1:<你的代理端口>
#                      （也可以不填这里，临时用环境变量：export GH_PROXY=...）
#   DEFAULT_REPO       默认仓库。例：<owner>/<repo>
#                      留空 = 运行时用当前目录 git 仓库的 origin 推断
#   DEFAULT_BASE       提 PR 的目标分支。默认 main，按需改成 master 等
#   DEFAULT_LOGIN      你的 GitHub 登录名（提 PR 时组成 head=登录名:分支）
#                      留空 = 运行时自动查询
# =============================================================================
GH_PROXY_FALLBACK=""      # ← 例：socks5h://127.0.0.1:<你的代理端口>
DEFAULT_REPO=""           # ← 例：<owner>/<repo>
DEFAULT_BASE="main"       # ← 例：main / master
DEFAULT_LOGIN=""          # ← 例：<你的 GitHub 登录名>

GH_PROXY="${GH_PROXY:-$GH_PROXY_FALLBACK}"   # 环境变量优先，其次用上面的默认值

API="https://api.github.com"
GH_API_VERSION="2022-11-28"
HTTP_CODE=""; BODY=""; TOKEN=""; PY=""

die()  { printf '✗ %s\n' "$*" >&2; exit 1; }
info() { printf '· %s\n' "$*"; }
ok()   { printf '✓ %s\n' "$*"; }

find_python() {
  [ -n "${PYTHON:-}" ] && { echo "$PYTHON"; return; }
  local c
  for c in python python3 py; do command -v "$c" >/dev/null 2>&1 && { echo "$c"; return; }; done
  c=$(ls -d /c/Users/*/AppData/Local/Programs/Python/*/python.exe 2>/dev/null | head -1)
  [ -n "$c" ] && { echo "$c"; return; }
  die "找不到 python（组装 JSON 需要；可用 PYTHON=... 指定）"
}
PY="$(find_python)"

load_token() {
  [ -n "$TOKEN" ] && return
  TOKEN=$(printf 'protocol=https\nhost=github.com\n\n' \
    | GIT_TERMINAL_PROMPT=0 timeout 25 git credential fill 2>/dev/null \
    | sed -n 's/^password=//p')
  [ -n "$TOKEN" ] || die "取不到 GitHub 令牌（请先在 Git 里登录一次 GitHub）"
}

# repo_from_git [目录] → owner/name
repo_from_git() {
  local dir="${1:-.}" url
  url=$(git -C "$dir" remote get-url origin 2>/dev/null) || return 1
  printf '%s' "$url" | sed -E 's#^git@github\.com:#https://github.com/#' \
    | sed -E 's#^(https?://[^/]+/)##; s#\.git$##; s#/+$##'
}

# 统一解析公共参数：`--flag value` 与 `--flag=value` 都支持
# 解析后 REPO / DIR 就位，其余进 ARGS
REPO=""; DIR="."
parse_common() {
  local -a raw=("$@") norm=()
  local i=0 tok
  while [ $i -lt ${#raw[@]} ]; do
    tok="${raw[$i]}"
    case "$tok" in
      --repo|--dir|--base|--head|--state|--limit|--reason)
        norm+=("$tok=${raw[$((i + 1))]:-}"); i=$((i + 2)) ;;
      *) norm+=("$tok"); i=$((i + 1)) ;;
    esac
  done
  ARGS=(); REPO=""; DIR="."
  for tok in "${norm[@]}"; do
    case "$tok" in
      --repo=*) REPO="${tok#*=}" ;;
      --dir=*)  DIR="${tok#*=}" ;;
      *) ARGS+=("$tok") ;;
    esac
  done
}
resolve_repo() {
  [ -n "$REPO" ] && return 0
  # ★ 配置区填了 DEFAULT_REPO 就用它，否则从当前目录的 git origin 推断
  [ -n "$DEFAULT_REPO" ] && { REPO="$DEFAULT_REPO"; return 0; }
  REPO=$(repo_from_git "$DIR") || die "无法从 $DIR 的 git remote origin 推断仓库：请加 --repo <owner>/<repo>，或在脚本「用之前先看这里」配置区填 DEFAULT_REPO"
}
my_login() {
  load_token
  gh_api GET /user >/dev/null
  printf '%s' "$BODY" | "$PY" -c 'import json,sys;print(json.load(sys.stdin)["login"])'
}

gh_api() {
  local method="$1" path="$2" payload="${3:-}" resp
  local args=(-s -X "$method"
              -H "Authorization: token $TOKEN"
              -H "Accept: application/vnd.github+json"
              -H "X-GitHub-Api-Version: $GH_API_VERSION"
              -w $'\n%{http_code}')
  [ -n "${GH_PROXY:-}" ] && args+=(-x "$GH_PROXY")   # 例：socks5h://127.0.0.1:<你的代理端口>
  [ -n "$payload" ] && args+=(--data-binary "@$payload")
  resp=$(curl "${args[@]}" "$API$path") || die "curl 失败：$path"
  HTTP_CODE=$(printf '%s' "$resp" | tail -n1)
  BODY=$(printf '%s' "$resp" | sed '$d')
}

show_http_error() {
  printf '✗ HTTP %s\n' "$HTTP_CODE" >&2
  printf '%s\n' "$BODY" | head -c 600 >&2; printf '\n' >&2
  case "$HTTP_CODE" in
    401) info "令牌无效/过期 → 清掉凭据管理器里的 github.com 条目后重新登录" >&2 ;;
    403) info "权限不足或被限流 → 令牌需 repo 权限；改 workflow 文件需 workflow 权限" >&2 ;;
    404) info "仓库或编号不存在，或令牌无权访问私有库" >&2 ;;
    422) info "参数不对：常见于同 head 已有 open PR、base 分支名写错、标签不存在" >&2 ;;
  esac
}
mk_temp() { mktemp -t ghsh.XXXXXX 2>/dev/null || mktemp; }
need_yes() { [ "${1:-}" = "1" ] || die "这是写操作（会改动别人可见的状态）：先拿到用户明确授权，再加 --yes 执行"; }

# ---------------- 子命令 ----------------
cmd_help() { sed -n '2,40p' "$0" | sed 's/^# \{0,1\}//'; }

cmd_token_check() {
  load_token
  gh_api GET /user
  [ "$HTTP_CODE" = "200" ] || { show_http_error; exit 1; }
  local login; login=$(printf '%s' "$BODY" | "$PY" -c 'import json,sys;d=json.load(sys.stdin);print(d["login"])')
  ok "令牌可用：login=$login（令牌长度 ${#TOKEN}，值不外显）"
}

cmd_repo_info() {
  parse_common "$@"; resolve_repo
  printf '仓库：%s\n' "$REPO"
  printf '本地目录：%s\n' "$(git -C "$DIR" rev-parse --show-toplevel 2>/dev/null || echo '(非 git 仓库)')"
}

cmd_verify() {
  local branch="main"; parse_common "$@"
  local b; for b in "${ARGS[@]}"; do [ -n "$b" ] && branch="$b"; done
  [ -d "$DIR/.git" ] || git -C "$DIR" rev-parse --git-dir >/dev/null 2>&1 || die "不是 git 仓库：$DIR"
  resolve_repo
  local lh rh
  lh=$(git -C "$DIR" rev-parse HEAD) || die "读本地 HEAD 失败"
  load_token
  gh_api GET "/repos/$REPO/commits/$branch"
  [ "$HTTP_CODE" = "200" ] || { show_http_error; exit 1; }
  rh=$(printf '%s' "$BODY" | "$PY" -c 'import json,sys;print(json.load(sys.stdin)["sha"])')
  printf '本地 HEAD      : %s\n' "${lh:0:12}"
  printf '远程 %-9s: %s\n' "$branch" "${rh:0:12}"
  printf '未提交/未跟踪  : %s 个文件\n' "$(git -C "$DIR" status --porcelain | wc -l | tr -d ' ')"
  if [ "$lh" = "$rh" ]; then ok "本地 = 远程（一致）"; else info "不一致 → 需要 push 或 fetch"; fi
}

cmd_pr_list() {
  local state="open"
  parse_common "$@"
  local a
  for a in "${ARGS[@]}"; do
    case "$a" in
      --state=*) state="${a#*=}" ;;
      open|closed|all) state="$a" ;;
      *) die "未知参数：$a（用法：pr-list [--repo owner/name] [--state open|closed|all]）" ;;
    esac
  done
  resolve_repo
  load_token
  gh_api GET "/repos/$REPO/pulls?state=$state&per_page=50"
  [ "$HTTP_CODE" = "200" ] || { show_http_error; exit 1; }
  printf '%s' "$BODY" | "$PY" -c '
import json,sys
d=json.load(sys.stdin)
if not d: print("（没有 PR）"); raise SystemExit
for p in d:
    print("#%-6s %-7s %-22s %s" % (p["number"], p["state"], p["head"]["label"][:22], p["title"][:60]))
'
}

cmd_pr_create() {
  local title="${1:-}"; shift || true
  local bodyfile="${1:-}"; shift || true
  [ -n "$title" ] && [ -n "$bodyfile" ] || die '用法：pr-create "<标题>" <正文.md> [--repo owner/name] [--base main] [--head owner:branch] [--dry-run] [--yes]'
  [ -f "$bodyfile" ] || die "正文文件不存在：$bodyfile"
  local base="${DEFAULT_BASE:-main}" head="" dry=0 yes=0
  parse_common "$@"
  local a; for a in "${ARGS[@]}"; do
    case "$a" in
      --base=*) base="${a#*=}" ;;
      --head=*) head="${a#*=}" ;;
      --dry-run) dry=1 ;;
      --yes) yes=1 ;;
      main|master) base="$a" ;;
      *) die "未知参数：$a" ;;
    esac
  done
  resolve_repo
  if [ -z "$head" ]; then
    local br login; br=$(git -C "$DIR" rev-parse --abbrev-ref HEAD 2>/dev/null || echo main)
    login="${DEFAULT_LOGIN:-$(my_login)}"   # ★ 配置区填了 DEFAULT_LOGIN 就不去查 API
    head="$login:$br"
  fi
  local ho="${head%%:*}" hb="${head##*:}"

  load_token
  gh_api GET "/repos/$REPO/pulls?state=open&head=$ho:$hb&per_page=50"
  [ "$HTTP_CODE" = "200" ] || { show_http_error; exit 1; }
  local dup; dup=$(printf '%s' "$BODY" | "$PY" -c 'import json,sys;print(len(json.load(sys.stdin)))')
  if [ "$dup" != "0" ]; then
    info "防重复预检：该 head 已有 open PR"
    printf '%s' "$BODY" | "$PY" -c 'import json,sys
for p in json.load(sys.stdin): print("   #%s %s\n       %s" % (p["number"], p["title"][:60], p["html_url"]))'
    die "已存在同 head 的 open PR，不再重复创建"
  fi

  local payload; payload=$(mk_temp)
  "$PY" - "$payload" "$title" "$head" "$base" "$bodyfile" <<'PYEOF'
import json, sys
out, title, head, base, bodyfile = sys.argv[1:6]
json.dump({"title": title, "head": head, "base": base,
           "maintainer_can_modify": True,
           "body": open(bodyfile, encoding="utf-8").read()},
          open(out, "w", encoding="utf-8"), ensure_ascii=False)
PYEOF
  info "仓库=$REPO  head=$head  base=$base  正文=$(wc -c <"$bodyfile" | tr -d ' ') 字节"
  info "标题：$title"
  if [ "$dry" = "1" ]; then info "--dry-run：未提交（仅预览正文前 400 字）"; head -c 400 "$bodyfile"; printf '\n'; rm -f "$payload"; return 0; fi
  need_yes "$yes"
  gh_api POST "/repos/$REPO/pulls" "$payload"; rm -f "$payload"
  [ "$HTTP_CODE" = "201" ] || { show_http_error; exit 1; }
  ok "PR 已创建"
  printf '%s' "$BODY" | "$PY" -c 'import json,sys;d=json.load(sys.stdin);print("  #%s  %s\n  %s" % (d["number"], d["title"], d["html_url"]))'
}

cmd_issue_list() {
  local state="open" limit="20"; parse_common "$@"
  local a; for a in "${ARGS[@]}"; do
    case "$a" in --state=*) state="${a#*=}" ;; --limit=*) limit="${a#*=}" ;; *) die "未知参数：$a" ;; esac
  done
  resolve_repo; load_token
  gh_api GET "/repos/$REPO/issues?state=$state&per_page=$limit"
  [ "$HTTP_CODE" = "200" ] || { show_http_error; exit 1; }
  printf '%s' "$BODY" | "$PY" -c '
import json,sys
for i in json.load(sys.stdin):
    if "pull_request" in i: continue
    lab = ",".join(l["name"] for l in i.get("labels", []))
    print("#%-6s %-6s %-20s %s" % (i["number"], i["state"], ("["+lab+"]") if lab else "", i["title"][:70]))
'
}

cmd_issue_show() {
  local num="${1:-}"; shift || true
  [ -n "$num" ] || die "用法：issue-show <编号> [--repo owner/name]"
  parse_common "$@"; resolve_repo; load_token
  gh_api GET "/repos/$REPO/issues/$num"
  [ "$HTTP_CODE" = "200" ] || { show_http_error; exit 1; }
  local tmp; tmp=$(mk_temp); printf '%s' "$BODY" >"$tmp"
  "$PY" - "$tmp" <<'PYEOF'
import json, sys
d = json.load(open(sys.argv[1], encoding="utf-8"))
print("标题  : %s" % d["title"])
print("状态  : %s  comments=%s  作者=%s  更新=%s" % (d["state"], d["comments"], d["user"]["login"], d["updated_at"][:19]))
print("标签  : %s" % ", ".join(l["name"] for l in d.get("labels", [])))
print("链接  : %s" % d["html_url"])
print("-" * 70)
print((d.get("body") or "")[:3000])
PYEOF
  rm -f "$tmp"
  gh_api GET "/repos/$REPO/issues/$num/comments?per_page=20"
  [ "$HTTP_CODE" = "200" ] || return 0
  printf '%s' "$BODY" | "$PY" -c '
import json,sys
for c in json.load(sys.stdin):
    print("-"*70); print("[%s @ %s]" % (c["user"]["login"], c["created_at"][:19])); print((c.get("body") or "")[:1200])
'
}

cmd_issue_create() {
  local title="${1:-}"; shift || true
  local bodyfile="${1:-}"; shift || true
  [ -n "$title" ] && [ -n "$bodyfile" ] || die '用法：issue-create "<标题>" <正文.md> [--repo owner/name] [--dry-run] [--yes]'
  [ -f "$bodyfile" ] || die "正文文件不存在：$bodyfile"
  local dry=0 yes=0; parse_common "$@"
  local a; for a in "${ARGS[@]}"; do case "$a" in --dry-run) dry=1 ;; --yes) yes=1 ;; *) die "未知参数：$a" ;; esac; done
  resolve_repo
  local payload; payload=$(mk_temp)
  "$PY" - "$payload" "$title" "$bodyfile" <<'PYEOF'
import json, sys
out, title, bodyfile = sys.argv[1:4]
json.dump({"title": title, "body": open(bodyfile, encoding="utf-8").read()},
          open(out, "w", encoding="utf-8"), ensure_ascii=False)
PYEOF
  info "仓库=$REPO  标题=$title"
  if [ "$dry" = "1" ]; then info "--dry-run：未提交"; head -c 400 "$bodyfile"; printf '\n'; rm -f "$payload"; return 0; fi
  need_yes "$yes"; load_token
  gh_api POST "/repos/$REPO/issues" "$payload"; rm -f "$payload"
  [ "$HTTP_CODE" = "201" ] || { show_http_error; exit 1; }
  ok "issue 已创建"
  printf '%s' "$BODY" | "$PY" -c 'import json,sys;d=json.load(sys.stdin);print("  #%s  %s\n  %s" % (d["number"], d["title"], d["html_url"]))'
}

cmd_issue_comment() {
  local num="${1:-}"; shift || true
  local bodyfile="${1:-}"; shift || true
  [ -n "$num" ] && [ -n "$bodyfile" ] || die '用法：issue-comment <编号> <正文.md> [--repo owner/name] [--dry-run] [--yes]'
  [ -f "$bodyfile" ] || die "正文文件不存在：$bodyfile"
  local dry=0 yes=0; parse_common "$@"
  local a; for a in "${ARGS[@]}"; do case "$a" in --dry-run) dry=1 ;; --yes) yes=1 ;; *) die "未知参数：$a" ;; esac; done
  resolve_repo
  local payload; payload=$(mk_temp)
  "$PY" - "$payload" "$bodyfile" <<'PYEOF'
import json, sys
out, bodyfile = sys.argv[1:3]
json.dump({"body": open(bodyfile, encoding="utf-8").read()}, open(out, "w", encoding="utf-8"), ensure_ascii=False)
PYEOF
  info "目标：$REPO #$num"
  if [ "$dry" = "1" ]; then info "--dry-run：未发送"; head -c 400 "$bodyfile"; printf '\n'; rm -f "$payload"; return 0; fi
  need_yes "$yes"; load_token
  gh_api POST "/repos/$REPO/issues/$num/comments" "$payload"; rm -f "$payload"
  [ "$HTTP_CODE" = "201" ] || { show_http_error; exit 1; }
  ok "评论已发送"
  printf '%s' "$BODY" | "$PY" -c 'import json,sys;print("  "+json.load(sys.stdin)["html_url"])'
}

cmd_issue_label() {
  local num="${1:-}"; shift || true
  local labels="${1:-}"; shift || true
  [ -n "$num" ] && [ -n "$labels" ] || die '用法：issue-label <编号> "bug,help wanted" [--repo ...] [--yes]'
  local yes=0; parse_common "$@"
  local a; for a in "${ARGS[@]}"; do case "$a" in --yes) yes=1 ;; *) die "未知参数：$a" ;; esac; done
  need_yes "$yes"; resolve_repo
  local payload; payload=$(mk_temp)
  "$PY" - "$payload" "$labels" <<'PYEOF'
import json, sys
out, labels = sys.argv[1:3]
json.dump({"labels": [s.strip() for s in labels.split(",") if s.strip()]}, open(out, "w", encoding="utf-8"), ensure_ascii=False)
PYEOF
  load_token
  gh_api POST "/repos/$REPO/issues/$num/labels" "$payload"; rm -f "$payload"
  [ "$HTTP_CODE" = "200" ] || { show_http_error; exit 1; }
  ok "标签已更新（$labels）"
}

cmd_issue_close() {
  local num="${1:-}"; shift || true
  local yes=0 reason="completed"; parse_common "$@"
  local a; for a in "${ARGS[@]}"; do
    case "$a" in --yes) yes=1 ;; --reason=*) reason="${a#*=}" ;; completed|not_planned) reason="$a" ;; *) die "未知参数：$a" ;; esac
  done
  [ -n "$num" ] || die "用法：issue-close <编号> [--reason completed|not_planned] [--yes]"
  need_yes "$yes"; resolve_repo
  local payload; payload=$(mk_temp)
  "$PY" - "$payload" "$reason" <<'PYEOF'
import json, sys
out, reason = sys.argv[1:3]
json.dump({"state": "closed", "state_reason": reason}, open(out, "w", encoding="utf-8"))
PYEOF
  load_token
  gh_api PATCH "/repos/$REPO/issues/$num" "$payload"; rm -f "$payload"
  [ "$HTTP_CODE" = "200" ] || { show_http_error; exit 1; }
  ok "issue #$num 已关闭（reason=$reason）"
}

# 逃生口：只读用 GET 最安全；POST/PATCH/DELETE 要求 --yes
cmd_api() {
  local method="${1:-GET}" path="${2:-}"; shift 2 || true
  local payload="${1:-}" yes=0
  [ $# -gt 0 ] && shift
  while [ $# -gt 0 ]; do case "$1" in --yes) yes=1 ;; esac; shift; done
  [ -n "$path" ] || die "用法：api <GET|POST|PATCH|DELETE> <path> [payload.json] [--yes]"
  [ "$method" = "GET" ] || need_yes "$yes"
  load_token
  gh_api "$method" "$path" "$payload"
  printf '%s\n' "HTTP $HTTP_CODE"
  printf '%s\n' "$BODY" | head -c 4000
  printf '\n'
}

cmd="${1:-help}"; shift || true
case "$cmd" in
  help|-h|--help) cmd_help ;;
  token-check)    cmd_token_check ;;
  repo-info)      cmd_repo_info "$@" ;;
  verify)         cmd_verify "$@" ;;
  pr-list)        cmd_pr_list "$@" ;;
  pr-create)      cmd_pr_create "$@" ;;
  issue-list)     cmd_issue_list "$@" ;;
  issue-show)     cmd_issue_show "$@" ;;
  issue-create)   cmd_issue_create "$@" ;;
  issue-comment)  cmd_issue_comment "$@" ;;
  issue-label)    cmd_issue_label "$@" ;;
  issue-close)    cmd_issue_close "$@" ;;
  api)            cmd_api "$@" ;;
  *) printf '未知子命令：%s\n\n' "$cmd" >&2; cmd_help >&2; exit 1 ;;
esac
