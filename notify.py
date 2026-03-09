"""Send Telegram notifications for whitelist hits."""
import os
import requests

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "8744489466")


def send_telegram(message: str):
    if not TELEGRAM_TOKEN:
        print(f"[WARNING] No TELEGRAM_BOT_TOKEN set — would have sent:\n{message}")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    resp = requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}, timeout=10)
    if resp.status_code == 200:
        print("[OK] Notification sent")
    else:
        print(f"[ERROR] Telegram failed: {resp.text}")


def notify_hits(hits: list[dict]):
    if not hits:
        print("[INFO] No whitelist hits found")
        return

    lines = [f"🍷 <b>{len(hits)} whitelist hit{'s' if len(hits) > 1 else ''}</b>\n"]
    for h in hits:
        lines.append(
            f"• <b>{h['matched_producer']}</b> — {h['name']}\n"
            f"  {h['source']} · {h.get('price', '')} · <a href=\"{h['url']}\">View</a>"
        )
        if h.get("styles"):
            lines.append(f"  <i>{h['styles']}</i>")
        lines.append("")

    send_telegram("\n".join(lines))
