#!/usr/bin/env python3
"""
Heti jelentés generáló — hétfő reggel fut
"""
import json
import os
from datetime import datetime, timedelta, timezone

import db
from notify import format_item_card, send_telegram


def generate_weekly(profile=None):
    """Heti összefoglaló generálása és elküldése"""
    if profile is None:
        profiles = db.get_active_profiles()
    else:
        profiles = [profile]

    today = datetime.now(timezone.utc)
    week_ago = (today - timedelta(days=7)).strftime("%Y-%m-%d")
    week_str = f"{week_ago} — {today.strftime('%Y-%m-%d')}"

    for prof in profiles:
        items = db.get_weekly_items(week_ago)
        profile_groups = json.loads(prof["product_groups"]) if isinstance(prof["product_groups"], str) else prof["product_groups"]

        # Szűrés profilra
        filtered = []
        for item in items:
            item_groups = item.get("product_groups", "[]")
            if isinstance(item_groups, str):
                try:
                    item_groups = json.loads(item_groups)
                except:
                    item_groups = []
            if not item_groups or any(g in profile_groups for g in item_groups):
                filtered.append(item)

        # Kategorizálás
        categories = {"jogszabaly": [], "riasztas": [], "szabvany": [], "egyeb": []}
        for item in filtered:
            cat = item.get("category", "egyeb")
            if cat not in categories:
                cat = "egyeb"
            categories[cat].append(item)

        lines = [
            f"🍽️ **Heti Élelmiszer-jogfigyelő**",
            f"📅 {week_str}",
            f"👤 {prof['name']}",
            f"📊 {len(filtered)} releváns változás a héten\n",
        ]

        emoji_map = {"jogszabaly": "🔴", "riasztas": "🟡", "szabvany": "🔵", "egyeb": "⚪"}
        label_map = {"jogszabaly": "JOGSZABÁLY", "riasztas": "RIASZTÁS", "szabvany": "SZABVÁNY", "egyeb": "EGYÉB"}

        for cat in ["jogszabaly", "riasztas", "szabvany", "egyeb"]:
            cat_items = categories[cat]
            if not cat_items:
                continue
            lines.append(f"{emoji_map[cat]} **{label_map[cat]}** ({len(cat_items)})")
            for item in cat_items:
                lines.append(format_item_card(item))
                lines.append("")

        if not filtered:
            lines.append("✅ Nincs releváns változás ezen a héten.")

        message = "\n".join(lines)
        send_telegram(message, prof.get("notification_target"))

    print(f"✅ Heti jelentés elkészítve: {len(profiles)} profilnak")


if __name__ == "__main__":
    generate_weekly()