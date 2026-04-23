"""Shared filtering rules for rectg crawler and maintenance scripts."""
from __future__ import annotations

import re
from datetime import datetime
from typing import Mapping, Any

import opencc


MIN_CHANNEL_SUBSCRIBERS = 1000
MIN_GROUP_MEMBERS = 200
INACTIVE_DAYS_THRESHOLD = 90
TRADITIONAL_RATIO_THRESHOLD = 0.10

CJK_RE = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff]")
T2S_CONVERTER = opencc.OpenCC("t2s")

# Keep this list to clearly illegal/high-risk terms. Do not include terms that
# have first-class categories in this project, such as VPN/proxy resources.
HARMFUL_KEYWORDS = [
    "博彩", "赌场", "资金盘", "跑分", "枪支", "迷药", "催情", "迷幻",
    "洗钱", "提现", "查档", "开房记录", "社工库", "呼死你", "轰炸机",
    "菠菜", "嫩模", "外围", "约炮", "迷奸", "代开发票", "黑产", "网赚",
    "色流", "彩票", "赌博", "百家乐", "六合彩", "棋牌", "网赌",
    "破解盗刷", "莞式", "全套", "品茶", "修车", "同城群", "约妹",
]

PROHIBITED_CONTEXT_RE = re.compile(
    r"(禁止|严禁|不准|不允许|拒绝|谢绝|请勿).*?"
    r"(黑产|广告|博彩|赌博|色情|黄赌毒|政治|违法犯罪)",
    re.IGNORECASE,
)


def contains_chinese(text: str) -> bool:
    return bool(CJK_RE.search(text)) if text else False


def is_traditional_chinese(text: str) -> bool:
    if not text:
        return False

    cjk_chars = CJK_RE.findall(text)
    if len(cjk_chars) < 5:
        return False

    simplified = T2S_CONVERTER.convert(text)
    diff_count = sum(1 for before, after in zip(text, simplified) if before != after)
    return diff_count / max(len(text), 1) >= TRADITIONAL_RATIO_THRESHOLD


def is_harmful(text: str) -> bool:
    if not text:
        return False

    text_to_check = PROHIBITED_CONTEXT_RE.sub("", text.lower())
    return any(keyword in text_to_check for keyword in HARMFUL_KEYWORDS)


def inactive_days(last_active: str | None) -> int:
    if not last_active:
        return 0

    try:
        dt_str = last_active.replace("+00:00", "").replace("Z", "")
        last_dt = datetime.fromisoformat(dt_str)
        return (datetime.now() - last_dt).days
    except (ValueError, TypeError):
        return 0


def evaluate_entry(entry: Mapping[str, Any]) -> tuple[int, str]:
    """Return (keep, reason) for a crawled Telegram entry."""
    if not entry.get("valid"):
        return 0, "链接无效"
    if entry.get("private"):
        return 0, "私密频道/群组"

    entry_type = entry.get("type")
    if not entry_type:
        return 0, "无法识别类型"

    text = f"{entry.get('title') or ''} {entry.get('description') or ''}"
    if not contains_chinese(text):
        return 0, "非中文内容"
    if is_traditional_chinese(text):
        return 0, "繁体中文内容"
    if is_harmful(text):
        return 0, "有害内容"

    count = entry.get("count") or 0
    if entry_type == "channel":
        if count < MIN_CHANNEL_SUBSCRIBERS:
            return 0, f"订阅数不足 ({count} < {MIN_CHANNEL_SUBSCRIBERS})"

        days = inactive_days(entry.get("last_active"))
        if days > INACTIVE_DAYS_THRESHOLD:
            return 0, f"频道不活跃 ({days}天未更新)"
    elif entry_type == "group":
        if count < MIN_GROUP_MEMBERS:
            return 0, f"成员数不足 ({count} < {MIN_GROUP_MEMBERS})"
    elif entry_type == "bot":
        if count == 0:
            return 0, "无月活用户数据"

    return 1, ""
