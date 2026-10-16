"""
Play Store Update Notifier
--------------------------
Checks every app listed in apps.txt on the Google Play Store.
When an app gets a new update, sends a WhatsApp message (CallMeBot)
and an email (Gmail) at the same time.

Settings come from environment variables (GitHub Secrets):
  WhatsApp option A - Green-API (used if GREENAPI_INSTANCE_ID is set):
  GREENAPI_URL         apiUrl shown in your Green-API console (e.g. https://7103.api.greenapi.com)
  GREENAPI_INSTANCE_ID idInstance from the console
  GREENAPI_TOKEN       apiTokenInstance from the console
  WHATSAPP_TO          your main WhatsApp number, country code, no + (e.g. 923001234567)
  WhatsApp option B - CallMeBot:
  CALLMEBOT_PHONE      your WhatsApp number with country code, no + (e.g. 923001234567)
  CALLMEBOT_APIKEY     the key CallMeBot sends you on WhatsApp
  GMAIL_ADDRESS        the Gmail account that sends the email
  GMAIL_APP_PASSWORD   16-character Gmail app password
  EMAIL_TO             (optional) where to send the email; defaults to GMAIL_ADDRESS

Run modes:
  python notifier.py          normal check
  python notifier.py --test   send a test message on both channels and exit
"""

import json
import os
import smtplib
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from email.mime.text import MIMEText
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
APPS_FILE = BASE_DIR / "apps.txt"
STATE_FILE = BASE_DIR / "state.json"

PKT = timezone(timedelta(hours=5))          # Pakistan time for message timestamps
FAIL_ALERT_AFTER = 6                        # failed checks in a row before an error alert (~30 min)
HIDDEN_VERSIONS = {None, "", "VARY", "Varies with device"}


# ---------------------------------------------------------------- helpers

def now_pkt() -> str:
    return datetime.now(PKT).strftime("%d %b %Y, %I:%M %p PKT")


def fmt_ts(ts) -> str:
    if not ts:
        return "Not shown"
    return datetime.fromtimestamp(int(ts), PKT).strftime("%d %b %Y, %I:%M %p PKT")


def clean_version(v):
    return None if v in HIDDEN_VERSIONS else v


def play_link(pkg: str) -> str:
    return f"https://play.google.com/store/apps/details?id={pkg}"


def load_apps() -> list[str]:
    apps = []
    for line in APPS_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        # accept full Play links or bare package names
        if "id=" in line:
            line = urllib.parse.parse_qs(urllib.parse.urlparse(line).query).get("id", [line])[0]
        apps.append(line)
    return apps


def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return {"apps": {}}


def save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


# ---------------------------------------------------------------- Play Store

def fetch_app(pkg: str) -> dict:
    """Return title / version / updated timestamp for one app."""
    from google_play_scraper import app as gp_app

    last_err = None
    for attempt in range(3):
        try:
            d = gp_app(pkg, lang="en", country="us")
            return {
                "title": d.get("title") or pkg,
                "version": clean_version(d.get("version")),
                "updated": d.get("updated"),
                "changes": (d.get("recentChanges") or "").strip(),
            }
        except Exception as e:  # network hiccup or Play page change
            last_err = e
            time.sleep(3 * (attempt + 1))
    raise RuntimeError(f"Could not read Play Store page: {last_err}")


def is_new_update(old: dict, new: dict) -> bool:
    if new.get("updated") and new["updated"] != old.get("updated"):
        return True
    if new.get("version") and old.get("version") and new["version"] != old["version"]:
        return True
    return False


# ---------------------------------------------------------------- notifications

def send_whatsapp(text: str) -> bool:
    """Green-API if its secrets are set, otherwise CallMeBot."""
    if os.getenv("GREENAPI_INSTANCE_ID", "").strip():
        return send_whatsapp_greenapi(text)
    return send_whatsapp_callmebot(text)


def send_whatsapp_greenapi(text: str) -> bool:
    api_url = os.getenv("GREENAPI_URL", "").strip().rstrip("/") or "https://api.green-api.com"
    inst = os.getenv("GREENAPI_INSTANCE_ID", "").strip()
    token = os.getenv("GREENAPI_TOKEN", "").strip()
    to = os.getenv("WHATSAPP_TO", "").strip().lstrip("+").replace(" ", "")
    if not (inst and token and to):
        print("WhatsApp (Green-API): skipped (secrets not set)")
        return False
    url = f"{api_url}/waInstance{inst}/sendMessage/{token}"
    payload = json.dumps({"chatId": f"{to}@c.us", "message": text}).encode("utf-8")
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, data=payload, method="POST",
                                         headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=30) as r:
                body = r.read().decode("utf-8", "ignore")
            if r.status == 200 and "idMessage" in body:
                print("WhatsApp (Green-API): sent")
                return True
            print(f"WhatsApp (Green-API): unexpected reply: {body[:200]}")
        except Exception as e:
            print(f"WhatsApp (Green-API): attempt {attempt + 1} failed: {e}")
        time.sleep(5 * (attempt + 1))
    return False


def send_whatsapp_callmebot(text: str) -> bool:
    phone = os.getenv("CALLMEBOT_PHONE", "").strip()
    key = os.getenv("CALLMEBOT_APIKEY", "").strip()
    if not phone or not key:
        print("WhatsApp (CallMeBot): skipped (secrets not set)")
        return False
    url = "https://api.callmebot.com/whatsapp.php?" + urllib.parse.urlencode(
        {"phone": phone, "text": text, "apikey": key}
    )
    for attempt in range(3):
        try:
            with urllib.request.urlopen(url, timeout=30) as r:
                body = r.read().decode("utf-8", "ignore")
            if r.status == 200 and "error" not in body.lower():
                print("WhatsApp: sent")
                return True
            print(f"WhatsApp: unexpected reply: {body[:200]}")
        except Exception as e:
            print(f"WhatsApp: attempt {attempt + 1} failed: {e}")
        time.sleep(5 * (attempt + 1))
    return False


def send_email(subject: str, text: str) -> bool:
    user = os.getenv("GMAIL_ADDRESS", "").strip()
    pwd = os.getenv("GMAIL_APP_PASSWORD", "").replace(" ", "").strip()
    to = os.getenv("EMAIL_TO", "").strip() or user
    if not user or not pwd:
        print("Email: skipped (secrets not set)")
        return False
    msg = MIMEText(text, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = user
    msg["To"] = to
    for attempt in range(3):
        try:
            with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as s:
                s.login(user, pwd)
                s.sendmail(user, [to], msg.as_string())
            print("Email: sent")
            return True
        except Exception as e:
            print(f"Email: attempt {attempt + 1} failed: {e}")
            time.sleep(5 * (attempt + 1))
    return False


def notify(subject: str, text: str) -> bool:
    """Send on both channels. True if at least one worked."""
    wa = send_whatsapp(text)
    em = send_email(subject, text)
    return wa or em


def update_message(pkg: str, info: dict, old: dict) -> tuple[str, str]:
    lines = [
        f"🔔 New update: {info['title']}",
        "",
        f"Version: {info['version'] or 'Not shown'}",
    ]
    if old.get("version") and info.get("version") and old["version"] != info["version"]:
        lines.append(f"Previous: {old['version']}")
    lines += [
        f"Updated on Play: {fmt_ts(info.get('updated'))}",
        f"Detected: {now_pkt()}",
    ]
    if info.get("changes"):
        changes = info["changes"]
        if len(changes) > 500:
            changes = changes[:500] + "..."
        lines += ["", "What's new:", changes]
    lines += ["", play_link(pkg)]
    subject = f"New update: {info['title']}" + (f" ({info['version']})" if info.get("version") else "")
    return subject, "\n".join(lines)


# ---------------------------------------------------------------- main

def run_check() -> None:
    apps = load_apps()
    state = load_state()
    state.setdefault("apps", {})

    for pkg in apps:
        old = state["apps"].get(pkg, {})
        try:
            info = fetch_app(pkg)
        except Exception as e:
            old["fail_count"] = old.get("fail_count", 0) + 1
            print(f"[{pkg}] check failed ({old['fail_count']}): {e}")
            if old["fail_count"] == FAIL_ALERT_AFTER:
                notify(
                    f"Update checker problem: {pkg}",
                    f"⚠️ Update checker could not read the Play Store page for {pkg} "
                    f"for about 30 minutes.\n\nLast error: {e}\n\n{play_link(pkg)}\n\n"
                    "It will keep trying and tell you when it works again.",
                )
            state["apps"][pkg] = old
            continue

        if old.get("fail_count", 0) >= FAIL_ALERT_AFTER:
            notify(f"Update checker working again: {info['title']}",
                   f"✅ Update checker is working again for {info['title']}.")

        if "updated" not in old:
            # first time seeing this app: save a baseline, no alert
            print(f"[{pkg}] baseline saved: version={info['version']} updated={fmt_ts(info['updated'])}")
            state["apps"][pkg] = {**info, "fail_count": 0}
            continue

        if is_new_update(old, info):
            subject, text = update_message(pkg, info, old)
            print(f"[{pkg}] NEW UPDATE detected")
            if notify(subject, text):
                state["apps"][pkg] = {**info, "fail_count": 0}
            else:
                # neither channel worked: keep old state so the next run retries the alert
                print(f"[{pkg}] both channels failed; will retry next run")
                old["fail_count"] = 0
                state["apps"][pkg] = old
        else:
            print(f"[{pkg}] no change (version={info['version']}, updated={fmt_ts(info['updated'])})")
            state["apps"][pkg] = {**info, "fail_count": 0}

    # changes once per day so GitHub sees regular activity and keeps the schedule alive
    state["heartbeat"] = datetime.now(PKT).strftime("%Y-%m-%d")
    save_state(state)


def run_test() -> None:
    apps = load_apps()
    text = (
        "✅ Play Store update notifier is set up.\n\n"
        f"Watching {len(apps)} app(s):\n" + "\n".join(f"- {a}" for a in apps) +
        f"\n\nTest sent: {now_pkt()}"
    )
    ok = notify("Play Store notifier: test message", text)
    if not ok:
        sys.exit("Test failed on both channels. Check your secrets.")


if __name__ == "__main__":
    if "--test" in sys.argv:
        run_test()
    else:
        run_check()
