import json
import os
import re
import smtplib
from datetime import date
from email.message import EmailMessage
from pathlib import Path

import requests

BASE_DIR = Path(__file__).parent
PRODUCTS_FILE = BASE_DIR / "products.json"
HISTORY_FILE = BASE_DIR / "price_history.json"

GMAIL_EMAIL = os.environ["GMAIL_EMAIL"]
GMAIL_APP_PASSWORD = os.environ["GMAIL_APP_PASSWORD"]
NOTIFY_TO = os.environ.get("NOTIFY_TO", GMAIL_EMAIL)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
}

PRICE_RE = re.compile(r'data-sticky-add-to-cart-price="\$([\d,]+\.\d{2})"')


def fetch_price(url):
    resp = requests.get(url, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    match = PRICE_RE.search(resp.text)
    if not match:
        raise ValueError(f"price not found on page: {url}")
    return float(match.group(1).replace(",", ""))


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
    products = json.loads(PRODUCTS_FILE.read_text())
    history = json.loads(HISTORY_FILE.read_text()) if HISTORY_FILE.exists() else {}

    today = date.today().isoformat()

    for product in products:
        code = product["code"]
        name = product["name"]
        url = product["url"]

        price = fetch_price(url)
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

        history[code] = {"date": today, "price": price}

    HISTORY_FILE.write_text(json.dumps(history, indent=2) + "\n")


if __name__ == "__main__":
    main()
