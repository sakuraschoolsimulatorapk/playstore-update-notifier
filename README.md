# Play Store Update Notifier

Checks your apps on Google Play every 5 minutes and sends you a **WhatsApp message + email** when any of them gets a new update. It runs free on GitHub's servers, so your PC and phone can be off.

## File structure (keep exactly like this)

```
playstore-update-notifier/
├── .github/
│   └── workflows/
│       └── check.yml       ← the 5-minute timer (path must be exact)
├── apps.txt                ← list of apps to watch (edit this to add apps)
├── notifier.py             ← the checker
├── requirements.txt
└── README.md
```

`state.json` is created automatically on the first run. Don't create it yourself.

## Setup

### 1. Set up WhatsApp (pick ONE option)

**Option A: Green-API (recommended, works now)**
You link a **spare WhatsApp number**, which then sends alerts to your **main WhatsApp**.
Don't link your main number. This is an unofficial API, and WhatsApp may block a linked number.
1. Put a spare SIM in a spare phone and make sure WhatsApp is active on it.
2. Sign up at https://console.green-api.com and create an instance on the free **Developer** plan.
3. In the instance, scan the QR code with the spare phone (WhatsApp → Linked devices → Link a device).
4. From the instance page, copy **apiUrl**, **idInstance** and **apiTokenInstance**.
5. From your main phone, send any WhatsApp message to the spare number once, so the chat exists.

**Option B: CallMeBot (only if their bot has free slots)**
1. On your phone, open https://www.callmebot.com/blog/free-api-whatsapp-messages/
2. Save the bot's WhatsApp number shown on that page to your contacts.
3. Send it this exact message on WhatsApp: `I allow callmebot to send me messages`
4. It replies with your **API key**. Keep it.

### 2. Get a Gmail app password (5 min)
1. Your Google account must have **2-Step Verification** turned on.
2. Open https://myaccount.google.com/apppasswords
3. Create one named `Play notifier`. Copy the 16-character password.

### 3. Create the GitHub repo
1. Create a free account at github.com if you don't have one.
2. New repository → name `playstore-update-notifier` → **Public** → Create.
   (Public gives unlimited free run time. Your keys stay hidden in Secrets; only the app list is visible.)
3. Click **uploading an existing file** → drag in `notifier.py`, `apps.txt`, `requirements.txt`, `README.md` → Commit.
4. Add the workflow file: **Add file → Create new file**. In the name box type exactly
   `.github/workflows/check.yml` (the slashes create the folders), paste the contents of `check.yml`, then Commit.

### 4. Add your secrets
Repo → **Settings → Secrets and variables → Actions → New repository secret**. Add these one by one:

| Name | Value |
|---|---|
| **If Option A (Green-API):** | |
| `GREENAPI_URL` | apiUrl from the console, e.g. `https://7103.api.greenapi.com` |
| `GREENAPI_INSTANCE_ID` | idInstance |
| `GREENAPI_TOKEN` | apiTokenInstance |
| `WHATSAPP_TO` | Your **main** WhatsApp number, country code, no `+`, e.g. `923001234567` |
| **If Option B (CallMeBot):** | |
| `CALLMEBOT_PHONE` | Your WhatsApp number with country code, no `+` or spaces, e.g. `923001234567` |
| `CALLMEBOT_APIKEY` | The key from step 1 |
| **Email (always):** | |
| `GMAIL_ADDRESS` | Your Gmail address |
| `GMAIL_APP_PASSWORD` | The 16-character app password from step 2 |
| `EMAIL_TO` | (Optional) a different address to receive alerts. Skip to send to yourself. |

### 5. Send a test message
Repo → **Actions** tab → if asked, click **"I understand my workflows, go ahead and enable them"** →
**Check Play Store updates** → **Run workflow** → tick **"Send a test message"** → Run.
Within a minute you should get the test on WhatsApp and email.

### 6. Start monitoring
Run the workflow once more **without** the tick. This saves the current version of each app (no alert).
From then on it checks every 5 minutes by itself.

## Adding more apps
Open `apps.txt` on GitHub → pencil icon → add a Play link or package name on a new line → Commit.
The first check of a new app saves its baseline silently; alerts start from its next update.

## What the alerts look like
```
🔔 New update: SAKURA School Simulator

Version: 1.047.13            (or "Not shown" if Google hides it)
Updated on Play: 16 Oct 2026, 11:42 PM PKT
Detected: 16 Oct 2026, 11:47 PM PKT

What's new:
Bug fixes

https://play.google.com/store/apps/details?id=jp.garud.ssimulator
```

You also get:
- **⚠️ Problem alert** if the Play page can't be read for about 30 minutes, and **✅ working again** when it recovers.
- No alert is lost: if both WhatsApp and email fail, it retries on the next run.

## Notes
- GitHub can run the 5-minute timer a few minutes late at busy times.
- The checker saves a small daily change to `state.json`, which keeps GitHub from pausing the timer for inactivity.
- To stop it: Actions tab → Check Play Store updates → `...` → Disable workflow.
