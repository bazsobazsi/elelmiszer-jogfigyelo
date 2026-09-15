#!/usr/bin/env python3
"""
Értesítő modul — Telegram + e-mail
"""
import json
import os
import subprocess
import db


def format_item_card(item):
    """Egy item-ből kártya formátumú szöveg"""
    emoji_map = {
        "eurlex": "🔴",
        "rasff": "🟡",
        "kozlony": "🔵",
        "nebih": "📘",
        "szabvany": "🟣",
    }
    source_emoji = emoji_map.get(item.get("source", ""), "📄")
    category = item.get("category", "egyeb")
    cat_label = {"jogszabaly": "JOGSZABÁLY", "riasztas": "RIASZTÁS", "szabvany": "SZABVÁNY"}.get(category, "EGYÉB")

    lines = [
        f"{source_emoji} **{cat_label}** ({item['source'].upper()})",
        f"📄 {item['title'][:100]}",
    ]

    product_groups = item.get("product_groups", "[]")
    if isinstance(product_groups, str):
        try:
            product_groups = json.loads(product_groups)
        except (json.JSONDecodeError, TypeError):
            product_groups = []
    if product_groups:
        lines.append(f"🏷️ {', '.join(product_groups[:4])}")

    standards = item.get("standards_affected", "[]")
    if isinstance(standards, str):
        try:
            standards = json.loads(standards)
        except (json.JSONDecodeError, TypeError):
            standards = []
    if standards:
        lines.append(f"📋 Érintett: {', '.join(standards[:4])}")

    if item.get("impact_summary"):
        lines.append(f"📝 {item['impact_summary'][:200]}")

    if item.get("action_required"):
        lines.append(f"⚡ {item['action_required'][:150]}")

    if item.get("deadline"):
        lines.append(f"⏰ Határidő: {item['deadline']}")

    if item.get("url"):
        lines.append(f"🔗 {item['url']}")

    return "\n".join(lines)


def send_telegram(message, chat_id=None):
    """
    Telegram üzenet küldése Hermes cron output-on keresztül.
    A cron job automatikusan elküldi a stdout-ot a cél chat-be.
    """
    if chat_id:
        print(f"---TELEGRAM_CHAT:{chat_id}---")
    print(message)


def format_daily_digest(items, profile_name="Ügyfél"):
    """Napi digest formázása"""
    if not items:
        return f"✅ **{profile_name}** — nincs releváns változás ma."

    categories = {"jogszabaly": [], "riasztas": [], "szabvany": [], "egyeb": []}
    for item in items:
        cat = item.get("category", "egyeb")
        if cat not in categories:
            cat = "egyeb"
        categories[cat].append(item)

    emoji_map = {"jogszabaly": "🔴", "riasztas": "🟡", "szabvany": "🔵", "egyeb": "⚪"}
    label_map = {"jogszabaly": "JOGSZABÁLY", "riasztas": "RIASZTÁS", "szabvany": "SZABVÁNY", "egyeb": "EGYÉB"}

    lines = [
        f"🍽️ **Élelmiszer-jogfigyelő** — {profile_name}",
        f"📊 {len(items)} releváns változás\n",
    ]

    for cat_key in ["jogszabaly", "riasztas", "szabvany", "egyeb"]:
        cat_items = categories[cat_key]
        if not cat_items:
            continue
        lines.append(f"{emoji_map[cat_key]} **{label_map[cat_key]}** ({len(cat_items)} db)\n")
        for item in cat_items:
            lines.append(format_item_card(item))
            lines.append("")

    return "\n".join(lines)


def send_daily_digest(profile=None):
    """Napi digest összeállítása és elküldése"""
    import db
    from datetime import datetime, timezone

    if profile is None:
        profiles = db.get_active_profiles()
    else:
        profiles = [profile]

    for prof in profiles:
        items = db.get_daily_digest()
        # Szűrés profil termékcsoportjaira
        profile_groups = json.loads(prof["product_groups"]) if isinstance(prof["product_groups"], str) else prof["product_groups"]
        filtered = []
        for item in items:
            item_groups = item.get("product_groups", "[]")
            if isinstance(item_groups, str):
                try:
                    item_groups = json.loads(item_groups)
                except (json.JSONDecodeError, TypeError):
                    item_groups = []
            if not item_groups or any(g in profile_groups for g in item_groups):
                filtered.append(item)

        message = format_daily_digest(filtered, prof["name"])
        send_telegram(message, prof.get("notification_target"))

        # Jelölés elküldöttként
        for item in filtered:
            db.mark_notified(prof["id"], item["id"])


if __name__ == "__main__":
    send_daily_digest()