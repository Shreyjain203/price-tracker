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


def send_email(subject, plain_body, html_body):
    msg = EmailMessage()
    msg["From"] = GMAIL_EMAIL
    msg["To"] = NOTIFY_TO
    msg["Subject"] = subject
    msg.set_content(plain_body)
    msg.add_alternative(html_body, subtype="html")

    with smtplib.SMTP("smtp.gmail.com", 587) as s:
        s.starttls()
        s.login(GMAIL_EMAIL, GMAIL_APP_PASSWORD)
        s.send_message(msg)


def build_card(name, code, url, old_price, new_price):
    dropped = new_price < old_price
    diff = abs(new_price - old_price)
    accent = "#16a34a" if dropped else "#dc2626"
    arrow = "↓" if dropped else "↑"
    verdict = (
        f"Down ${diff:,.2f}. Might be worth jumping on this one."
        if dropped
        else f"Up ${diff:,.2f}. Guess it's not the day to buy."
    )

    plain = (
        f"{name} ({code})\n{url}\n"
        f"${old_price:,.2f} -> ${new_price:,.2f}\n{verdict}\n"
    )

    html = f"""\
      <div style="background:#0b1f3a;padding:20px 24px;">
        <span style="color:#ffffff;font-size:13px;letter-spacing:.05em;
                     text-transform:uppercase;opacity:.7;">Price Watch</span>
        <h1 style="color:#ffffff;font-size:20px;margin:6px 0 0;">{name}</h1>
        <span style="color:#ffffff;opacity:.6;font-size:12px;">{code}</span>
      </div>
      <div style="padding:24px;">
        <table style="width:100%;border-collapse:collapse;margin-bottom:20px;">
          <tr>
            <td style="padding:10px 0;color:#8e8e93;font-size:13px;">Yesterday</td>
            <td style="padding:10px 0;text-align:right;font-size:15px;
                       color:#8e8e93;text-decoration:line-through;">
              ${old_price:,.2f}
            </td>
          </tr>
          <tr>
            <td style="padding:10px 0;color:#1c1c1e;font-size:13px;
                       border-top:1px solid #f0f0f2;">Today</td>
            <td style="padding:10px 0;text-align:right;font-size:22px;
                       font-weight:700;color:{accent};
                       border-top:1px solid #f0f0f2;">
              {arrow} ${new_price:,.2f}
            </td>
          </tr>
        </table>
        <p style="font-size:14px;color:#1c1c1e;background:#f5f5f7;
                  padding:12px 14px;border-radius:10px;margin:0 0 20px;">
          {verdict}
        </p>
        <a href="{url}" style="display:block;text-align:center;
                  background:{accent};color:#ffffff;text-decoration:none;
                  padding:12px 0;border-radius:10px;font-size:14px;
                  font-weight:600;">
          Check it out →
        </a>
      </div>
"""
    return plain, html


def send_summary_email(changes):
    n = len(changes)
    subject = (
        f"👀 Price moved on {changes[0]['name']}"
        if n == 1
        else f"👀 Price moved on {n} watches"
    )

    intro = "Yo 👋 the price just changed on this one." if n == 1 else \
        f"Yo 👋 {n} watches on your list just changed price."

    plain_parts = [intro, ""]
    html_cards = []
    for c in changes:
        plain, html = build_card(c["name"], c["code"], c["url"], c["old_price"], c["new_price"])
        plain_parts.append(plain)
        html_cards.append(f'<div style="border-radius:16px;overflow:hidden;border:1px solid #e5e5ea;margin-bottom:16px;">{html}</div>')

    plain_body = "\n".join(plain_parts)

    html_body = f"""\
<html>
  <body style="margin:0;padding:24px;background:#f5f5f7;
               font-family:-apple-system,Helvetica,Arial,sans-serif;">
    <div style="max-width:420px;margin:0 auto;">
      <p style="font-size:15px;color:#1c1c1e;margin:0 0 20px;">{intro}</p>
      {''.join(html_cards)}
    </div>
  </body>
</html>
"""
    send_email(subject, plain_body, html_body)


def main():
    links = read_links()
    history = json.loads(HISTORY_FILE.read_text()) if HISTORY_FILE.exists() else {}

    today = date.today().isoformat()
    changes = []

    for url in links:
        code, name, price = fetch_product(url)
        prev = history.get(code)

        if prev is not None and prev["price"] != price:
            changes.append({
                "code": code,
                "name": name,
                "url": url,
                "old_price": prev["price"],
                "new_price": price,
            })
            print(f"CHANGED {code}: {prev['price']} -> {price}")
        else:
            print(f"no change {code}: {price}")

        history[code] = {"date": today, "name": name, "url": url, "price": price}

    if changes:
        send_summary_email(changes)

    HISTORY_FILE.write_text(json.dumps(history, indent=2) + "\n")


if __name__ == "__main__":
    main()
