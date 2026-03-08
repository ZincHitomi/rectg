#!/usr/bin/env python3
"""
README.md 生成器
从 SQLite 数据库读取已经清洗和分类好的爬虫结果，生成更新后的 README.md。

用法:
    python3 scripts/generate_readme.py
"""
import argparse
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
DB_PATH = ROOT_DIR / "data" / "rectg.db"
README_PATH = ROOT_DIR / "README.md"

# 一级大类
TYPE_ORDER = [
    {"id": "channel", "name": "频道"},
    {"id": "group", "name": "群组"},
    {"id": "bot", "name": "机器人"},
]

# 二级分类排序规则（按照这个顺序输出二级分类）
CATEGORY_ORDER = [
    "🆕 新发现频道",
    "📰 新闻快讯",
    "💻 数码科技",
    "👨‍💻 开发运维",
    "🔒 信息安全",
    "🧰 软件工具",
    "☁️ 网盘资源",
    "🎬 影视剧集",
    "🎵 音乐音频",
    "🎐 动漫次元",
    "🎮 游戏娱乐",
    "✈️ 科学上网",
    "🪙 加密货币",
    "📚 学习阅读",
    "🎨 创意设计",
    "📡 社媒搬运",
    "🏀 体育运动",
    "👗 生活消费",
    "🌍 地区社群",
    "💬 闲聊交友",
    "🔞 福利吃瓜",
    "🗂️ 综合导航",
    "🌐 综合其他"
]

def make_anchor(section: str, category_index: int | None = None) -> str:
    """生成稳定锚点，避免依赖 GitHub 对中文/emoji 标题的默认锚点规则。"""
    if category_index is None:
        return f"section-{section}"
    return f"section-{section}-{category_index}"

def format_count(count) -> str:
    """格式化数字为精确数字字符串，带千分位逗号。"""
    if count is None:
        return "-"
    return f"{int(count):,}"

def escape_pipe(text: str) -> str:
    """转义 Markdown 表格中的管道符。"""
    if not text:
        return ""
    return text.replace("|", " / ").replace("\n", " ").strip()

def compact_text(text: str) -> str:
    """压缩多余空白，适合表格单元格。"""
    if not text:
        return ""
    return " ".join(text.split())

def generate_readme(conn: sqlite3.Connection) -> str:
    """从数据库生成 README.md 内容。"""
    rows = conn.execute("""
        SELECT type, category, clean_title, clean_desc, url, count, title, description
        FROM entries
        WHERE keep = 1
        ORDER BY count DESC
    """).fetchall()

    # 结构: stats[type_id][cat_name] = [item1, item2, ...]
    tree = {
        "channel": {},
        "group": {},
        "bot": {}
    }
    
    total_kept = len(rows)

    # 手动注入的新频道，在这里记录它们的 URL，避免在后续重复添加
    NEW_CHANNELS = [
        {"title": "副业", "url": "https://t.me/sidehustleus", "description": "关注副业赚钱、搞钱经验和独立开发", "count": None},
        {"title": "技术拾荒者", "url": "https://t.me/tech_scavenger", "description": "分享优质技术文章、开源项目与实用工具", "count": None},
        {"title": "一个人的产品", "url": "https://t.me/solo_product", "description": "独立开发者、产品设计与运营经验", "count": None},
        {"title": "深夜博客", "url": "https://t.me/late_night_blog", "description": "深夜阅读文章、个人随笔与精神角落", "count": None},
        {"title": "什么值得看", "url": "https://t.me/worth_read", "description": "推荐值得一读的好文章与好书", "count": None},
        {"title": "程序员日常", "url": "https://t.me/dev_everyday", "description": "程序员的日常工作、吐槽与经验分享", "count": None},
        {"title": "小众软件", "url": "https://t.me/niche_software", "description": "发现与分享好用、新奇的小众软件", "count": None},
        {"title": "酱酱の日报", "url": "https://t.me/jiangdaily", "description": "每天不只是新闻，更是酱酱的发现日常～ 精选有趣、有料、有灵魂的「热饭」", "count": 137},
        {"title": "财经速报", "url": "https://t.me/econ_news_cn", "description": "最新最快的财经新闻与市场动态资讯", "count": None}
    ]
    custom_urls = {ch["url"] for ch in NEW_CHANNELS}
    custom_rows = conn.execute("""
        SELECT url, count
        FROM entries
        WHERE url IN ({})
    """.format(",".join("?" for _ in custom_urls)), tuple(custom_urls)).fetchall()
    count_by_url = {
        row["url"]: row["count"]
        for row in custom_rows
        if row["count"] is not None
    }

    for row in rows:
        t = row["type"]
        if t not in tree:
            continue
            
        # 过滤掉自定义注入的频道，防止重复
        if row["url"] in custom_urls:
            continue

        cat = row["category"] or "🌐 综合其他"
        if cat not in tree[t]:
            tree[t][cat] = []
        tree[t][cat].append(dict(row))

    # 注入新频道板块
    tree["channel"]["🆕 新发现频道"] = [
        {
            "type": "channel",
            "category": "🆕 新发现频道",
            "clean_title": ch["title"],
            "title": ch["title"],
            "url": ch["url"],
            "count": count_by_url.get(ch["url"], ch["count"]),
            "clean_desc": ch["description"],
            "description": ch["description"]
        } for ch in NEW_CHANNELS
    ]

    type_counts = {}
    for t_id in tree:
        type_counts[t_id] = sum(len(items) for items in tree[t_id].values())

    lines = []
    lines.append("# rectg · Telegram 中文频道与群组精选")
    lines.append("")
    lines.append("> **rectg** 持续收录高质量 Telegram 中文频道与群组，结合自动化抓取与人工整理，尽量剔除失效链接、低质内容与长期停更条目，帮助你更高效地发现值得关注的 TG 资源。")
    lines.append("> ")
    lines.append("> **免责声明**：本项目基于公开互联网信息整理，仅供技术学习、信息导航与研究参考使用。请使用者自行甄别内容，并严格遵守所在地法律法规；因使用相关内容产生的风险与责任，由使用者自行承担。")
    lines.append("")

    lines.append("## 目录")
    lines.append("")

    for t_info in TYPE_ORDER:
        t_id = t_info["id"]
        categories = tree[t_id]
        if not categories:
            continue

        lines.append(f"- [{t_info['name']}](#{make_anchor(t_id)})")

        existing_cats = set(categories.keys())
        sorted_cats = [c for c in CATEGORY_ORDER if c in existing_cats]
        sorted_cats += sorted(list(existing_cats - set(CATEGORY_ORDER)))

        for idx, cat in enumerate(sorted_cats, start=1):
            lines.append(f"  - [{cat}](#{make_anchor(t_id, idx)})")

    lines.append("")

    # 生成各版块
    for t_info in TYPE_ORDER:
        t_id = t_info["id"]
        t_name = t_info["name"]
        
        categories = tree[t_id]
        if not categories:
            continue

        lines.append(f'<a id="{make_anchor(t_id)}"></a>')
        lines.append(f"## {t_name}")
        lines.append("")
        
        # 按照预定义的 category 顺序遍历，如果不在预定义里则放到最后
        existing_cats = set(categories.keys())
        sorted_cats = [c for c in CATEGORY_ORDER if c in existing_cats]
        sorted_cats += sorted(list(existing_cats - set(CATEGORY_ORDER)))
        
        for idx, cat in enumerate(sorted_cats, start=1):
            items = categories[cat]
            if not items:
                continue

            lines.append(f'<a id="{make_anchor(t_id, idx)}"></a>')
            lines.append("### " + cat)
            lines.append("")
            lines.append("| 名称 | 链接 | 订阅数 | 简介 |")
            lines.append("| --- | --- | ---: | --- |")

            for item in items:
                title = escape_pipe(compact_text(item.get("clean_title") or item.get("title") or ""))
                desc = escape_pipe(compact_text(item.get("clean_desc") or item.get("description") or "")) or "-"
                url = item.get("url", "")
                count = format_count(item.get("count"))
                lines.append(f"| {title} | [直达]({url}) | {count} | {desc} |")

            lines.append("")

    # Star History 保持在底部
    lines.append("## Star History")
    lines.append("")
    lines.append("[![Star History](https://starchart.cc/jackhawks/rectg.svg?variant=adaptive)](https://starchart.cc/jackhawks/rectg)")
    lines.append("")

    return "\n".join(lines).strip() + "\n"


def main():
    parser = argparse.ArgumentParser(description="README.md 生成器")
    parser.add_argument("--output", type=str, default=None, help="输出路径（默认覆盖 README.md）")
    args = parser.parse_args()

    if not DB_PATH.exists():
        print(f"❌ 未找到数据库: {DB_PATH}")
        sys.exit(1)

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row

    readme_content = generate_readme(conn)
    conn.close()

    out_path = Path(args.output) if args.output else README_PATH
    out_path.write_text(readme_content, encoding="utf-8")
    print(f"✅ README 已生成: {out_path}")


if __name__ == "__main__":
    main()
