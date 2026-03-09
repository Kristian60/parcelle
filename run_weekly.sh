#!/bin/bash
# Parcelle weekly monitor — scrape all shops and send Telegram notification
cd "$(dirname "$0")"

export TELEGRAM_BOT_TOKEN="8550847615:AAEavwd7soCO3mBuuMvVXR0jLr88mfuvEik"
export TELEGRAM_CHAT_ID="8744489466"

venv/bin/python monitor.py 2>&1
