import json
import os
import re
import smtplib
from datetime import date
from email.message import EmailMessage
from pathlib import Path

import requests

BASE_DIR = Path(__file__).parent
LINKS_FILE = BASE_DIR / "links.txt"
HISTORY_FILE = BASE_DIR / "price_history.json"

GMAIL_EMAIL = os.environ["GMAIL_EMAIL"]
GMAIL_APP_PASSWORD = os.environ["GMAIL_APP_PASSWORD"]
NOTIFY_TO = os.environ.get("NOTIFY_TO", GMAIL_EMAIL)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
}

PRICE_RE = re.compile(r'data-sticky-add-to-cart-price="\$([\d,]+\.\d{2})"')
ITEM_RE = re.compile(r'"item_id":"([^"]+)","item_name":"([^"]+)"')


def read_links():
    links = []
    for line in LINKS_FILE.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            links.append(line)
    return links


def fetch_product(url):
    resp = requests.get(url, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    html = resp.text

    price_match = PRICE_RE.search(html)
    if not price_match:
        raise ValueError(f"price not found on page: {url}")
    price = float(price_match.group(1).replace(",", ""))

    item_match = ITEM_RE.search(html)
    if item_match:
        code, name = item_match.group(1), item_match.group(2)
    else:
        code = url.rstrip("/").rsplit("/", 1)[-1].removesuffix(".html")
        name = code

    return code, name, price


def send_email(subject, body):
    msg = EmailMessage()
    msg["From"] = GMAIL_EMAIL
    msg["To"] = NOTIFY_TO
    msg["Subject"] = subject
    msg.set_content(body)

    with smtplib.SMTP("smtp.gmail.com", 587) as s:
        s.starttls()
        s.login(GMAIL_EMAIL, GMAIL_APP_PASSWORD)
        s.send_message(msg)


def main():
    links = read_links()
    history = json.loads(HISTORY_FILE.read_text()) if HISTORY_FILE.exists() else {}

    today = date.today().isoformat()

    for url in links:
        code, name, price = fetch_product(url)
        prev = history.get(code)

        if prev is not None and prev["price"] != price:
            send_email(
                f"Price change: {name} ({code})",
                f"{name} ({code})\n{url}\n\n"
                f"Yesterday ({prev['date']}): ${prev['price']:.2f}\n"
                f"Today ({today}): ${price:.2f}\n",
            )
            print(f"CHANGED {code}: {prev['price']} -> {price}")
        else:
            print(f"no change {code}: {price}")

        history[code] = {"date": today, "name": name, "url": url, "price": price}

    HISTORY_FILE.write_text(json.dumps(history, indent=2) + "\n")


if __name__ == "__main__":
    main()
