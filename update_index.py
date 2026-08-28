"""
网页索引生成器
功能：扫描指定目录的 HTML/PDF 文件，生成带树状图和可点击链接的 index.md

支持格式：.html, .htm, .pdf
"""
import os
from pathlib import Path
from datetime import datetime
from collections import defaultdict

# ==================== 配置区（可按需修改） ====================
NOTES_DIR = "."  # 笔记根目录（在目标目录执行即可）
OUTPUT_FILE = "_index.md"  # 生成的索引文件名
# 不想被索引的文件夹名称
IGNORE_DIRS = {".git", ".workbuddy", ".obsidian", "assets", "images", "附件", "__pycache__", "templates", "build"}
# 不想被索引的文件名（在根目录或子目录都会被忽略）
IGNORE_FILES = {"index.html", "index.md"}
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

def render_folder_list(tree, root_base, depth=0):
    """
    渲染文件夹列表
    - 主文件夹 (depth=0): H2 标题，无缩进
    - 其他（子文件夹、文件）: 缩进列表
    - root_base: 用于计算相对链接的原始根目录（Path 对象）
    - 所有层级只显示当前文件夹/文件名，不累积路径
    """
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
            lines.extend(render_folder_list(content, root_base, depth + 1))
        else:
            # 文件
            f = content
            link_path = "./" + f.relative_to(root_base).as_posix()
            display_name = f.name
            icon = get_file_icon(f.name)

            # 文件统一用缩进列表
            indent = "  " * max(1, depth)
            lines.append(f"{indent}- {icon} [{display_name}]({link_path})")

    return lines

def convert_to_ascii_tree(node):
    """将 folder_tree 转换为 ASCII 树状图需要的结构（文件节点转为 None）"""
    if isinstance(node, Path):
        return None
    return {k: convert_to_ascii_tree(v) for k, v in node.items()}

def generate_md_index(base_dir):
    base_path = Path(base_dir).resolve()
    print(f"[INFO] 正在扫描目录：{base_path}")

    # 收集所有支持的文件
    md_files = []
    for p in base_path.rglob("*"):
        if not p.is_file():
            continue
        if any(ignored in p.parts for ignored in IGNORE_DIRS):
            continue
        if p.name in IGNORE_FILES:
            continue
        if p.suffix.lower() not in SCAN_EXTENSIONS:
            continue
        md_files.append(p)

    if not md_files:
        print("[WARN] 未找到任何支持的文件。")
        return

    # 构建文件夹树
    folder_tree = build_folder_tree(md_files, base_path)

    # 生成 ASCII 树状图
    tree_dict = convert_to_ascii_tree(folder_tree)
    tree_lines = ["📂 根目录index"]
    tree_lines.extend(render_tree_ascii(tree_dict))
    tree_chart = "\n".join(tree_lines)

    # 生成 Markdown 正文
    md_content = [
        f"# 📚 我的知识库",
        f"",
        f"> 📅 索引更新：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | 📄 共 **{len(md_files)}** 篇笔记",
        f"",
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
        "## 📑 笔记目录（点击直接打开）",
        ""
    ]

    # 渲染文件夹列表
    folder_lines = render_folder_list(folder_tree, base_path)
    md_content.extend(folder_lines)

    # 写入文件
    output_path = base_path / OUTPUT_FILE
    output_path.write_text("\n".join(md_content), encoding="utf-8")
    print(f"[OK] 索引生成成功！")
    print(f"[OK] 文件位置：{output_path}")
    print(f"[OK] 用 Typora 打开即可查看树状图和目录。")

if __name__ == "__main__":
    generate_md_index(NOTES_DIR)
