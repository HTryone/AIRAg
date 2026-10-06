"""
索引生成器（一个脚本管两件事）

作用（默认两条都做）：
  1) 全貌.md —— 扫描库里所有条目，生成带树状图 + 一句话摘要的「全貌」视图，
     一级目录、二级目录、脚本附件都展示出来；
  2) 刷新根 INDEX.md 里的「条目」数字 —— 顶部总数 + 分类表每行 + 合计行
     （只改数字列，其他文字一律不动）。

分工（重要）：
  * **手工维护**：根 INDEX.md（分类导航、说明、加条目流程）、各类别目录里的 INDEX.md（条目表、备注）。
  * **自动产物**：根索引表格里的数字、全貌.md —— 都别手改，跑脚本即可。

定位：
  * **根 INDEX.md 是唯一维护入口**，手工改它；本脚本产出的是**派生文件**：
    `全貌.md` 和各目录的 `INDEX.md`，都**不要手改**。
  * 一句话说明从根 INDEX.md 的分类表里读出来，所以条目写进根索引后跑一次就同步了。

用法（在库根目录执行）：
    python update_index.py                 # 两件都做（全貌 + 子索引）
    python update_index.py --only full     # 只生成全貌
    python update_index.py --only sub      # 只生成子索引
    python update_index.py --check         # 只校验子索引是否与根索引一致（不写盘，可用于 CI）
    python update_index.py --dry-run       # 只报告将要写哪些文件（不写盘）

支持格式：.md, .html, .htm, .pdf（条目）；脚本/模板等作为「附件」跟随所在目录展示
"""
import argparse
import os
import re
import sys
from pathlib import Path
from datetime import datetime
from collections import defaultdict
from urllib.parse import unquote

# ==================== 配置区（可按需修改） ====================
NOTES_DIR = "."  # 笔记根目录（在目标目录执行即可）
OUTPUT_FILE = "全貌.md"  # 生成的全貌文件名（别用 _index.md，跟主索引 INDEX.md 太像，容易误改）
INDEX_FILE = "INDEX.md"  # 主索引，脚本从这里读每个条目的一句话说明
# 不想被索引的文件夹名称
IGNORE_DIRS = {".git", ".workbuddy", ".obsidian", ".DSH", "assets", "images", "附件", "__pycache__", "templates", "build"}
# 不想被索引的文件名（不区分大小写，根目录和子目录都生效）
# 注意：必须包含本脚本自己生成的那个文件，否则重复运行会把它自己扫进去，越跑越多
IGNORE_FILES = {"index.md", "index.html", "readme.md", "_index.md", "全貌.md", "memory.md"}
# 优先排在前面的文件名关键词（包含这些词的文件排前面）
PINNED_KEYWORDS = ["目录", "index", "Index", "README"]
# 固定在最后面的文件名关键词（包含这些词的文件排最后）
BOTTOM_KEYWORDS = ["后记", "personal"]
# 要扫描的文件扩展名（= 条目，计入条目数）
SCAN_EXTENSIONS = {".html", ".md", ".pdf"}
# 非文档产物（脚本 / 模板 / 配置）：跟随所在目录一起展示，但**不计入条目数**
ATTACHMENT_EXTENSIONS = {".sh", ".py", ".bat", ".cmd", ".ps1", ".json",
                         ".yaml", ".yml", ".toml", ".ini", ".conf", ".service"}
# 扩展名不规整的附件（按文件名关键词识别，例：servers.json.示例）
ATTACHMENT_NAME_KEYWORDS = (".示例", ".example", ".template", ".样例")
# ============================================================

# 图标映射
FILE_ICONS = {
    ".html": "🌐", ".htm": "🌐",
    ".pdf": "📕",
    ".sh": "🧩", ".bat": "🧩", ".cmd": "🧩", ".ps1": "🧩",
    ".py": "🐍",
    ".json": "📎", ".yaml": "📎", ".yml": "📎", ".toml": "📎",
    ".ini": "📎", ".conf": "📎", ".service": "📎",
}

def is_attachment(filename):
    """是不是非文档产物（脚本 / 模板 / 配置）：按扩展名或文件名关键词判断。

    这类文件跟随所在目录一起展示，但**不计入条目数**。
    """
    name = Path(filename).name
    if Path(name).suffix.lower() in ATTACHMENT_EXTENSIONS:
        return True
    return any(kw in name for kw in ATTACHMENT_NAME_KEYWORDS)

def get_file_icon(filename):
    """根据文件扩展名返回图标（附件后缀不规矩时给 📎）"""
    ext = Path(filename).suffix.lower()
    if ext in FILE_ICONS:
        return FILE_ICONS[ext]
    return "📎" if is_attachment(filename) else "📄"

def load_summaries(index_path):
    """从主索引 INDEX.md 里读出每个条目的一句话说明。

    不写死列位置：读到分类表的表头，就查出「条目」列和「说明」列各排第几，
    再按这个位置取本节的条目。主索引加列、调列顺序都不会让脚本失效。
    **每个分类各自认一次表头**，所以各节格式不一样也能各读各的。

    表头认不出来时退一步：数据行里第一个带链接的列当条目列，它后面一列当说明列。

    读不到主索引、或某个条目读不到说明，一律静默留空，不提示、不中断 ——
    全貌照常输出，没说明的条目只显示文件名，看得见布局就行。

    返回：{ 相对路径: 一句话 }
    """
    summaries = {}
    p = Path(index_path)
    if not p.is_file():
        return summaries

    link_re = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
    entry_col = None
    summary_col = None

    for line in p.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]

        # 跳过分隔行 |---|---|
        if all(set(c) <= set("-: ") for c in cells if c):
            continue

        # 表头行：更新列位置（每个分类各自认一次）
        found_entry = None
        found_summary = None
        for i, cell in enumerate(cells):
            if any(k in cell for k in ("条目", "标题")):
                found_entry = i
            elif any(k in cell for k in ("一句话", "说明")):
                found_summary = i
        if found_entry is not None and found_summary is not None:
            entry_col, summary_col = found_entry, found_summary
            continue

        # 数据行：用最近一次认到的列位置
        cur_entry = entry_col
        cur_summary = summary_col

        # 表头一直没认出来：按本行实际情况兜底，带链接的那列当条目列
        if cur_entry is None:
            for i, cell in enumerate(cells):
                if link_re.search(cell):
                    cur_entry = i
                    cur_summary = i + 1
                    break

        if cur_entry is None or cur_summary is None:
            continue
        if len(cells) <= max(cur_entry, cur_summary):
            continue

        match = link_re.search(cells[cur_entry])
        if not match:
            continue
        link = unquote(match.group(2)).replace("\\", "/").lstrip("./")
        summary = cells[cur_summary]
        if summary and not summary.startswith("-"):
            summaries[link] = summary

    return summaries

def count_files_in_tree(node):
    """递归统计树中的**条目**数量（文档；脚本/附件不计入）"""
    if isinstance(node, Path):
        return 1 if node.suffix.lower() in SCAN_EXTENSIONS else 0
    return sum(count_files_in_tree(v) for v in node.values())

def build_folder_tree(files, base_path):
    """构建文件夹树状结构，文件节点存储 Path 对象"""
    root = {}
    for file in files:
        rel = file.relative_to(base_path)
        parts = list(rel.parts)

        current = root
        for i, part in enumerate(parts):
            is_last = (i == len(parts) - 1)

            if is_last:
                current[part] = file  # 存储文件对象
            else:
                if part not in current:
                    current[part] = {}
                current = current[part]

    return root

def render_tree_ascii(tree, prefix="", is_last=True):
    """递归渲染树状字典为 ASCII 文本（用于树状图）"""
    lines = []
    def tree_sort_key(item):
        name, content = item
        # 文件(content=None)排后面，目录(content=dict)排前面
        is_file = content is None
        # 文件名包含关键词的优先排在同类型前面
        is_pinned = 1 if any(kw in name for kw in PINNED_KEYWORDS) else 2
        # 文件名包含底部关键词的排到最后
        is_bottom = 1 if any(kw in name for kw in BOTTOM_KEYWORDS) else 0
        return (is_bottom, is_file, is_pinned, name)

    items = sorted(tree.items(), key=tree_sort_key)

    for i, (name, content) in enumerate(items):
        is_last_item = (i == len(items) - 1)
        connector = "└── " if is_last_item else "├── "

        if content is None:
            icon = get_file_icon(name)
            lines.append(f"{prefix}{connector}{icon} {name}")
        else:
            lines.append(f"{prefix}{connector}📁 {name}")
            new_prefix = prefix + ("    " if is_last_item else "│   ")
            lines.extend(render_tree_ascii(content, new_prefix, is_last_item))

    return lines

def render_folder_list(tree, root_base, summaries=None, depth=0, rel_prefix=""):
    """
    渲染文件夹列表
    - 主文件夹 (depth=0): H2 标题，无缩进
    - 其他（子文件夹、文件）: 缩进列表
    - root_base: 用于计算相对链接的原始根目录（Path 对象）
    - summaries: { 相对路径: 一句话 }，有就附在文件名后面
    - 所有层级只显示当前文件夹/文件名，不累积路径
    """
    summaries = summaries or {}
    lines = []
    def sort_key(item):
        name, content = item
        # 目录排前面，文件排后面
        is_file = isinstance(content, Path)
        # 文件名包含关键词的优先排在同类型前面
        is_pinned = 1 if any(kw in name for kw in PINNED_KEYWORDS) else 2
        # 文件名包含底部关键词的排到最后
        is_bottom = 1 if any(kw in name for kw in BOTTOM_KEYWORDS) else 0
        return (is_bottom, is_file, is_pinned, name)

    items = sorted(tree.items(), key=sort_key)

    for name, content in items:
        if isinstance(content, dict):
            # 目录：只显示当前文件夹名，不累积路径
            file_count = count_files_in_tree(content)

            # 索引里可能直接写文件夹（组合体）：`NN-xxx/文件夹名/`
            rel_dir = f"{rel_prefix}{name}"
            folder_summary = (summaries.get(rel_dir)
                              or summaries.get(rel_dir + "/")
                              or summaries.get(rel_dir.rstrip("/")))
            tail = f" — {folder_summary}" if folder_summary else ""

            if depth == 0:
                # 主文件夹用 H2，无缩进
                lines.append(f"## 📁 {name}（{file_count} 篇）{tail}")
                lines.append("")
            else:
                # 其他层级用缩进列表，只显示当前文件夹名
                indent = "  " * depth
                lines.append(f"{indent}- 📁 **{name}/**（{file_count} 篇）{tail}")

            # 递归子内容（只用 rel_prefix 查索引，显示不累积路径）
            lines.extend(render_folder_list(content, root_base, summaries,
                                            depth + 1, rel_dir + "/"))
        else:
            # 文件
            f = content
            rel = f.relative_to(root_base).as_posix()
            link_path = "./" + rel
            display_name = f.name
            icon = get_file_icon(f.name)

            # 主索引里有说明就附在后面；脚本/附件没有说明，单独标一下
            summary = summaries.get(rel)
            if summary:
                suffix = f" — {summary}"
            elif is_attachment(f.name):
                suffix = "　📎 脚本/附件（不计入条目数）"
            else:
                suffix = ""

            # 文件统一用缩进列表
            indent = "  " * max(1, depth)
            lines.append(f"{indent}- {icon} [{display_name}]({link_path}){suffix}")

    return lines

def convert_to_ascii_tree(node):
    """将 folder_tree 转换为 ASCII 树状图需要的结构（文件节点转为 None）"""
    if isinstance(node, Path):
        return None
    return {k: convert_to_ascii_tree(v) for k, v in node.items()}

def generate_md_index(base_dir):
    """生成全貌视图。成功返回 True，失败返回 False（由调用方决定退出码）。"""
    base_path = Path(base_dir).resolve()
    print(f"[1/3] 扫描目录 {base_path}")

    # 收集所有支持的文件：条目（文档）+ 附件（脚本/模板等）
    md_files, att_files = [], []
    for p in base_path.rglob("*"):
        if not p.is_file():
            continue
        if any(ignored in p.parts for ignored in IGNORE_DIRS):
            continue
        if p.name.lower() in IGNORE_FILES:
            continue
        if p.suffix.lower() in SCAN_EXTENSIONS:
            md_files.append(p)
        elif is_attachment(p.name):
            att_files.append(p)

    if not md_files:
        print("      一个条目都没扫到 —— 目录是空的，还是排除名单把文件全滤掉了？")
        return False

    # 构建文件夹树
    folder_tree = build_folder_tree(md_files + att_files, base_path)

    # 按目录统计条目数（供头部汇总用）
    dir_counts = {}
    for f in md_files:
        parts = f.relative_to(base_path).parts
        if len(parts) > 1:
            dir_counts[parts[0]] = dir_counts.get(parts[0], 0) + 1
    summary_line = " | ".join(f"{k} {v} 篇" for k, v in sorted(dir_counts.items()))

    print(f"      扫到 {len(md_files)} 个条目 + {len(att_files)} 个脚本/附件，"
          f"分布在 {len(dir_counts)} 个目录")

    # 读出主索引里每个条目的一句话说明
    # 读不到就静默留空，这里只报读到了多少条
    print(f"[2/3] 读主索引 {INDEX_FILE}")
    summaries = load_all_summaries(base_path)
    print(f"      读到 {len(summaries)} 条说明")

    # 生成 ASCII 树状图
    tree_dict = convert_to_ascii_tree(folder_tree)
    tree_lines = ["📂 根目录"]
    tree_lines.extend(render_tree_ascii(tree_dict))
    tree_chart = "\n".join(tree_lines)

    # 生成 Markdown 正文
    md_content = [
        f"# 🗺️ 全貌视图",
        f"",
        f"> 📅 更新：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | 📄 共 **{len(md_files)}** 个条目"
        f" | 📎 脚本/附件 **{len(att_files)}** 个",
        f">",
        f"> 这是**自动生成的全貌视图**，用来一眼看清库里有什么。",
        f"> 主索引（按领域分类、AI 检索用）见 [INDEX.md](./INDEX.md)。",
        f"",
        "---",
        "",
        "## 📊 各目录条目数",
        "",
        summary_line,
        "",
        "---",
        "",
        "## 🗺️ 文件夹结构图",
        "",
        "```",
        tree_chart,
        "```",
        "",
        "---",
        "",
        "## 📑 全部文件（条目 + 脚本附件，点击直接打开）",
        ""
    ]

    # 渲染文件夹列表
    folder_lines = render_folder_list(folder_tree, base_path, summaries, 0, "")
    md_content.extend(folder_lines)

    # 写入文件
    print(f"[3/3] 写全貌文件 {OUTPUT_FILE}")
    output_path = base_path / OUTPUT_FILE
    try:
        output_path.write_text("\n".join(md_content), encoding="utf-8")
    except OSError as e:
        print(f"      写入失败：{e}")
        return False

    print(f"      已写入 {output_path}")
    matched = sum(1 for f in md_files
                  if f.relative_to(base_path).as_posix() in summaries)
    stray = len(summaries) - matched
    print(f"完成：{len(md_files)} 个条目（+ {len(att_files)} 个脚本/附件），"
          f"{matched} 个条目带说明"
          + (f"（另有 {stray} 条索引行没落到文件上，不影响显示）" if stray > 0 else ""))
    print("提示：全貌是生成物，不要手改，下次运行会覆盖。主索引仍是 INDEX.md。")
    return True

# ==================== 索引维护（根索引计数 + 全貌说明来源） ====================
# 模型：
#   手工维护 —— 根 INDEX.md（分类导航/说明/流程）、各类别目录里的 INDEX.md（条目表）
#   自动产物 —— 根索引表格里的「条目」数字、全貌.md
CATEGORY_INDEX = "INDEX.md"          # 每个类别目录里手工维护的条目索引
COUNT_LINE_RE = re.compile(r"^条目总数：\*\*(\d+)\*\*（单条 (\d+) \+ 模块 (\d+)）\s*$", re.M)
CELL_LINK_RE = re.compile(r"^\[([^\]]+)\]")


def category_dirs(root):
    """库里所有类别目录（顶层，排除忽略目录），按名字排序。"""
    return sorted([p for p in root.iterdir()
                   if p.is_dir() and p.name not in IGNORE_DIRS],
                  key=lambda x: x.name)


def scan_category_counts(root):
    """每类多少「条目」：该目录（含其子文件夹）里的文档数，INDEX.md 本身不算。"""
    counts = {}
    for d in category_dirs(root):
        counts[d.name] = len([p for p in d.rglob("*")
                              if p.is_file()
                              and p.name.lower() not in IGNORE_FILES
                              and p.suffix.lower() in SCAN_EXTENSIONS
                              and not any(ig in p.parts for ig in IGNORE_DIRS)])
    return counts


def scan_type_counts(root):
    """按各类别索引里的「类型」列统计 单条 / 模块 各多少。"""
    single = module = 0
    for d in category_dirs(root):
        idx = d / CATEGORY_INDEX
        if not idx.is_file():
            continue
        for line in idx.read_text(encoding="utf-8").splitlines():
            if not line.startswith("|"):
                continue
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) >= 3 and cells[0] in ("单条", "模块") and CELL_LINK_RE.match(cells[1]):
                if cells[0] == "单条":
                    single += 1
                else:
                    module += 1
    return single, module


def load_all_summaries(root):
    """从**所有** INDEX.md（根 + 各类别）里读「一句话」，键统一成「相对库根的路径」。

    类别索引里的链接是同目录相对路径 → 先按该索引所在目录解析，再换算成相对库根，
    这样全貌里每条都能对上（工具文件夹里那行说明文档也能对上）。
    """
    merged = {}
    indexes = [root / INDEX_FILE] + [d / CATEGORY_INDEX for d in category_dirs(root)]
    for idx in indexes:
        if not idx.is_file():
            continue
        for link, summary in load_summaries(idx).items():
            try:
                target = (idx.parent / link).resolve()
                if is_attachment(target.name):
                    continue          # 脚本/模板那行不算「条目说明」
                key = target.relative_to(root).as_posix()
            except ValueError:
                continue
            merged.setdefault(key, summary)
    return merged


def refresh_root_counts(root, dry_run=False, check=False):
    """刷新根索引里的「条目」数字（顶部总数 + 分类表每行 + 合计行）。

    只改数字列，其余文字一律不动。返回 (是否已是最新, 改动说明列表)。
    """
    p = root / INDEX_FILE
    if not p.is_file():
        raise SystemExit(f"读不到根索引：{p}")
    text = p.read_text(encoding="utf-8")
    counts = scan_category_counts(root)
    single, module = scan_type_counts(root)
    total = sum(counts.values())

    gap = (single + module) - total
    gap_msg = ""
    if gap:
        gap_msg = (f"  ⚠️ 索引登记 {single + module} 条 ≠ 目录里的条目文件 {total} 条（差 {gap}）"
                   f"：检查是否有行没建文件，或建了文件没登记")

    changes = []
    out = []
    for line in text.splitlines():
        s = line.strip()
        # 顶部「条目总数」行
        m = COUNT_LINE_RE.match(line)
        if m:
            newline = f"条目总数：**{total}**（单条 {single} + 模块 {module}）"
            if newline != line:
                changes.append(f"条目总数：{line} → {newline}")
                line = newline
        # 分类表 / 合计行的计数列
        elif s.startswith("|") and s.endswith("|"):
            cells = [c.strip() for c in s.strip("|").split("|")]
            if len(cells) >= 2 and cells[1].strip("*").isdigit():
                lm = CELL_LINK_RE.match(cells[0])
                label = lm.group(1) if lm else cells[0].strip("* ")
                new = None
                if label == "合计":
                    new = f"**{total}**"
                elif label in counts:
                    new = str(counts[label])
                if new is not None and new != cells[1]:
                    changes.append(f"{label}：{cells[1]} → {new}")
                    cells[1] = new
                    line = "| " + " | ".join(cells) + " |"
        out.append(line)

    new_text = "\n".join(out) + ("\n" if text.endswith("\n") else "")
    missing = [d.name for d in category_dirs(root) if not (d / CATEGORY_INDEX).is_file()]

    if check:
        print(f"[计数] 共 {len(counts)} 个类别，条目合计 {total}（单条 {single} + 模块 {module}）")
        if changes:
            print(f"  **有 {len(changes)} 处待刷新**：")
            for c in changes:
                print(f"    · {c}")
        else:
            print("  根索引计数已是最新 ✓")
        if missing:
            print(f"  ⚠️ 缺类别索引：{'、'.join(missing)}")
        if gap_msg:
            print(gap_msg)
        return (not changes) and (not missing) and (not gap), changes

    print(f"[计数] 共 {len(counts)} 个类别，条目合计 {total}（单条 {single} + 模块 {module}）")
    if missing:
        print(f"  ⚠️ 缺类别索引（请手工建）：{'、'.join(missing)}")
    if gap_msg:
        print(gap_msg)
    if not changes:
        print("  根索引计数已是最新，无需改动 ✓")
        return True, changes
    for c in changes:
        print(f"    · {'[dry-run] 将改' if dry_run else '✓ 改'} {c}")
    if not dry_run:
        p.write_text(new_text, encoding="utf-8", newline="\n")
        print(f"  已写入 {p.name}")
    return True, changes


def extract_summary(path):
    """从条目文件里提一句话：优先「**结论**：…」，其次正文第一段。"""
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""
    keep = []
    for raw_line in text.splitlines():
        s = raw_line.strip()
        if not s or s.startswith("#") or s.startswith(">") or s.startswith("<!--"):
            if keep:
                break
            continue
        if s.startswith("|") or s.startswith("```") or s.startswith("---"):
            if keep:
                break
            continue
        keep.append(s)
        if len(" ".join(keep)) > 110:
            break
    para = " ".join(keep).strip()
    para = re.sub(r"\*\*([^*]+)\*\*", r"\1", para)
    para = re.sub(r"`([^`]+)`", r"\1", para)
    para = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", para)
    para = para.replace("|", "/").strip()
    if len(para) > 3 and para[0] in "结论说明" and "：" in para[:12]:
        para = para.split("：", 1)[1].strip()
    return para[:80]


def file_kind(path, text=None):
    """粗略判类型：带「## 这是什么」结构（模块模板）→ 模块，否则 单条。"""
    if text is None:
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return "单条"
    return "模块" if "## 这是什么" in text else "单条"


def generate_category_indexes(root, dry_run=False, check=False):
    """按目录里的实际文件，重新生成各个大类目录的 INDEX.md。

    手工写过的「一句话」和「## 备注（历史）」都会保留；新文件自动补上（说明从正文提取）。
    返回 (处理的大类数, 需要刷新的列表)。
    """
    made, stale = 0, []
    for d in category_dirs(root):
        idx = d / CATEGORY_INDEX
        old = idx.read_text(encoding="utf-8") if idx.is_file() else ""
        old_rows = load_summaries(idx) if old else {}      # {文件名: 已有说明}
        old_types = {}
        for line in old.splitlines():
            if not line.startswith("|"):
                continue
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) >= 3 and cells[0] in ("单条", "模块"):
                tm = re.search(r"\]\(([^)]+)\)", cells[1])   # 按「链接目标」取，别用链接文字
                if tm:
                    old_types[unquote(tm.group(1))] = cells[0]
        note = ""
        pos = old.find("## 备注（历史）")
        if pos != -1:
            note = old[pos:].rstrip("\n")

        rows, folder_blocks = [], []
        for p in sorted(d.iterdir(), key=lambda x: x.name):
            if not p.is_file() or p.name.lower() in IGNORE_FILES:
                continue
            if p.suffix.lower() not in SCAN_EXTENSIONS:
                continue
            try:
                body = p.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                body = ""
            summary = old_rows.get(p.name) or extract_summary(p)
            kind = old_types.get(p.name) or file_kind(p, body)
            rows.append(f"| {kind} | [{p.name}]({p.name}) | {summary} |")

        for sub in sorted([x for x in d.iterdir()
                           if x.is_dir() and x.name not in IGNORE_DIRS], key=lambda x: x.name):
            sub_rows = []
            for p in sorted(sub.iterdir(), key=lambda x: x.name):
                if not p.is_file() or p.name.lower() in IGNORE_FILES:
                    continue
                link = f"{sub.name}/{p.name}"
                if p.suffix.lower() in SCAN_EXTENSIONS:
                    try:
                        body = p.read_text(encoding="utf-8")
                    except (OSError, UnicodeDecodeError):
                        body = ""
                    summary = old_rows.get(link) or extract_summary(p)
                    kind = old_types.get(link) or file_kind(p, body)
                    sub_rows.append(f"| {kind} | [{p.name}]({link}) | {summary} |")
                elif is_attachment(p.name):
                    sub_rows.append(f"| 附件 | [{p.name}]({link}) | 脚本 / 模板（不计入条目数） |")
            if sub_rows:
                folder_blocks.extend(["", f"### 📁 {sub.name}/", "",
                                      "| 类型 | 文件 | 一句话 |", "|---|---|---|", *sub_rows])

        lines = [
            f"# {d.name}",
            "",
            "> ⚙️ 本文件由 `update_index.py` **自动生成**（扫描本目录里的文件）：新加条目只要把文件"
            "放进本目录，再跑一次 `python update_index.py` 就会自动出现。请勿手改。",
            "> 分类总览见根目录 [`INDEX.md`](../INDEX.md)。",
            "",
            "| 类型 | 条目 | 一句话 |",
            "|---|---|---|",
            *rows,
        ]
        if folder_blocks:
            lines.extend(folder_blocks)
        if note:
            lines.extend(["", note])
        content = "\n".join(lines).rstrip("\n") + "\n"

        if check:
            same = (old == content)
            if not same:
                stale.append(d.name)
            print(f"  {'一致' if same else '**需要刷新**'}  {d.name}（{len(rows)} 条）")
        elif dry_run:
            print(f"  [dry-run] 将重写 {idx.relative_to(root)}（{len(rows)} 条）")
        else:
            if old != content:
                idx.write_text(content, encoding="utf-8", newline="\n")
                print(f"  ✓ {idx.relative_to(root)}（{len(rows)} 条）")
            else:
                print(f"  = {idx.relative_to(root)} 无变化（{len(rows)} 条）")
        made += 1

    if check:
        print(f"  共 {made} 个大类，需刷新 {len(stale)} 个"
              + (f"：{'、'.join(stale)}" if stale else ""))
    return made, stale


def main():
    ap = argparse.ArgumentParser(
        description="索引维护：生成各大类 INDEX.md（扫描目录）+ 刷新根 INDEX.md 数字 + 生成 全貌.md")
    ap.add_argument("--only", choices=("all", "sub", "counts", "full"), default="all",
                    help="all=三件都做（默认）；sub=只生成大类索引；counts=只刷根索引数字；full=只生成全貌")
    ap.add_argument("--check", action="store_true",
                    help="只校验：大类索引是否需要刷新、根索引计数是否最新（不写盘）")
    ap.add_argument("--dry-run", action="store_true", help="只报告将改什么，不写盘")
    args = ap.parse_args()

    ok = True
    root = Path(NOTES_DIR).resolve()

    # 顺序很重要：先按目录生成大类索引，再刷根索引数字（单条/模块 是从大类索引里数的）
    if args.only in ("all", "sub"):
        try:
            _, stale = generate_category_indexes(root, dry_run=args.dry_run, check=args.check)
            if args.check and stale:
                ok = False
        except Exception as e:
            print(f"[ERROR] 生成大类索引出错：{e}")
            ok = False

    if args.only in ("all", "counts"):
        try:
            same, _ = refresh_root_counts(root, dry_run=args.dry_run, check=args.check)
            ok = same and ok
        except Exception as e:
            print(f"[ERROR] 刷新根索引计数出错：{e}")
            ok = False

    if args.only in ("all", "full"):
        if args.check:
            print("[全貌] --check 模式下不生成")
        elif args.dry_run:
            print(f"[全貌] [dry-run] 将重写 {OUTPUT_FILE}")
        else:
            try:
                ok = generate_md_index(NOTES_DIR) and ok
            except Exception as e:
                print(f"[ERROR] 生成全貌出错：{e}")
                ok = False

    if not ok:
        print("有需要处理的项目，见上面提示。")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
