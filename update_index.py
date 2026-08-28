"""
全貌视图生成器

作用：扫描库里所有条目文件，生成一份带树状图和一句话摘要的「全貌」文件，
      用来一眼看清整个库有什么、每个文件讲什么。

定位：这是**辅助视图**，不是主索引。
      主索引是 INDEX.md（按领域分类、带一句话说明，给 AI 检索用）。
      本文件是文件树视角，给人看全貌用。

一句话说明是从 INDEX.md 的分类表里读出来的，
所以条目写进主索引后，跑一次脚本全貌里就带上了。

支持格式：.html, .htm, .pdf, .md
"""
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
IGNORE_DIRS = {".git", ".workbuddy", ".obsidian", "assets", "images", "附件", "__pycache__", "templates", "build"}
# 不想被索引的文件名（不区分大小写，根目录和子目录都生效）
# 注意：必须包含本脚本自己生成的那个文件，否则重复运行会把它自己扫进去，越跑越多
IGNORE_FILES = {"index.md", "index.html", "readme.md", "_index.md", "全貌.md"}
# 优先排在前面的文件名关键词（包含这些词的文件排前面）
PINNED_KEYWORDS = ["目录", "index", "Index", "README"]
# 固定在最后面的文件名关键词（包含这些词的文件排最后）
BOTTOM_KEYWORDS = ["后记", "personal"]
# 要扫描的文件扩展名
SCAN_EXTENSIONS = {".html", ".md", ".pdf"}
# ============================================================

# 图标映射
FILE_ICONS = {
    ".html": "🌐", ".htm": "🌐",
    ".pdf": "📕",
}

def get_file_icon(filename):
    """根据文件扩展名返回图标"""
    ext = Path(filename).suffix.lower()
    return FILE_ICONS.get(ext, "📄")

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
    """递归统计树中文件数量"""
    if isinstance(node, Path):
        return 1
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

def render_folder_list(tree, root_base, summaries=None, depth=0):
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

            if depth == 0:
                # 主文件夹用 H2，无缩进
                lines.append(f"## 📁 {name}（{file_count} 篇）")
                lines.append("")
            else:
                # 其他层级用缩进列表，只显示当前文件夹名
                indent = "  " * depth
                lines.append(f"{indent}- 📁 **{name}/**（{file_count} 篇）")

            # 递归子内容，不传递路径前缀
            lines.extend(render_folder_list(content, root_base, summaries, depth + 1))
        else:
            # 文件
            f = content
            rel = f.relative_to(root_base).as_posix()
            link_path = "./" + rel
            display_name = f.name
            icon = get_file_icon(f.name)

            # 主索引里有说明就附在后面
            summary = summaries.get(rel)
            suffix = f" — {summary}" if summary else ""

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

    # 收集所有支持的文件
    md_files = []
    for p in base_path.rglob("*"):
        if not p.is_file():
            continue
        if any(ignored in p.parts for ignored in IGNORE_DIRS):
            continue
        if p.name.lower() in IGNORE_FILES:
            continue
        if p.suffix.lower() not in SCAN_EXTENSIONS:
            continue
        md_files.append(p)

    if not md_files:
        print("      一个条目都没扫到 —— 目录是空的，还是排除名单把文件全滤掉了？")
        return False

    # 构建文件夹树
    folder_tree = build_folder_tree(md_files, base_path)

    # 按目录统计条目数（供头部汇总用）
    dir_counts = {}
    for f in md_files:
        parts = f.relative_to(base_path).parts
        if len(parts) > 1:
            dir_counts[parts[0]] = dir_counts.get(parts[0], 0) + 1
    summary_line = " | ".join(f"{k} {v} 篇" for k, v in sorted(dir_counts.items()))

    print(f"      扫到 {len(md_files)} 个条目，分布在 {len(dir_counts)} 个目录")

    # 读出主索引里每个条目的一句话说明
    # 读不到就静默留空，这里只报读到了多少条
    print(f"[2/3] 读主索引 {INDEX_FILE}")
    summaries = load_summaries(base_path / INDEX_FILE)
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
        f"> 📅 更新：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | 📄 共 **{len(md_files)}** 个条目",
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
        "## 📑 全部条目（点击直接打开）",
        ""
    ]

    # 渲染文件夹列表
    folder_lines = render_folder_list(folder_tree, base_path, summaries)
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
    print(f"完成：{len(md_files)} 个条目，其中 {len(summaries)} 条带说明")
    print("提示：全貌是生成物，不要手改，下次运行会覆盖。主索引仍是 INDEX.md。")
    return True

if __name__ == "__main__":
    try:
        ok = generate_md_index(NOTES_DIR)
    except Exception as e:
        print(f"[ERROR] 出错了：{e}")
        ok = False
    sys.exit(0 if ok else 1)
