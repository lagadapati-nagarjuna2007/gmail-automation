# Gmail AI Agent – Free Setup Guide (Railway)

No VPS needed. 100% free.

---

## What You Need (All Free)

| Service | Purpose | Free? |
|---------|---------|-------|
| Google Cloud | Gmail API + OAuth | ✅ Free |
| Railway | Host the agent 24/7 | ✅ $5 credit/month |
| Supabase | Database | ✅ Free tier |
| Groq | AI analysis | ✅ Free tier |
| Telegram | Notifications | ✅ Free forever |

---

## STEP 1 — Google Cloud Setup

### 1.1 Create Project
1. Go to https://console.cloud.google.com
2. Click project dropdown → **New Project**
3. Name: `gmail-ai-agent` → Create

### 1.2 Enable Gmail API
1. APIs & Services → Enable APIs
2. Search **Gmail API** → Enable

### 1.3 Configure OAuth Consent Screen
1. APIs & Services → OAuth Consent Screen
2. User Type: **External** → Create
3. App name: `Gmail AI Agent`
4. Add your Gmail to **Test users**
5. Save and continue through all steps

### 1.4 Create OAuth Credentials
1. APIs & Services → Credentials → **+ Create Credentials → OAuth 2.0 Client ID**
2. Application type: **Web Application**
3. Authorized redirect URIs:
   ```
   https://yourapp.up.railway.app/auth/callback
   ```
   *(You'll get this URL after deploying to Railway in Step 4)*
4. Save your **Client ID** and **Client Secret**

---

## STEP 2 — Supabase Setup

1. Go to https://supabase.com → Sign up → **New Project**
2. Choose a region close to India (Singapore)
3. Once ready, go to **SQL Editor**
4. Open `app/database/schema.sql`, copy all contents, paste and **Run**
5. Go to **Settings → API**, copy:
   - **Project URL** → `SUPABASE_URL`
   - **service_role** key → `SUPABASE_KEY`

---

## STEP 3 — Telegram Bot

1. Open Telegram → Search **@BotFather** → `/newbot`
2. Name: `Gmail AI Agent`, Username: `yourgmailagent_bot`
3. Copy the **bot token**
4. Send `/start` to your bot, then open:
   ```
   https://api.telegram.org/bot<TOKEN>/getUpdates
   ```
5. Find `"chat":{"id": 123456789}` → copy your **Chat ID**

---

## STEP 4 — Deploy to Railway

### 4.1 Push code to GitHub
```bash
cd gmail-ai-agent
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/yourusername/gmail-ai-agent.git
git push -u origin main
```

### 4.2 Deploy on Railway
1. Go to https://railway.app → Sign up with GitHub
2. Click **New Project → Deploy from GitHub repo**
3. Select your `gmail-ai-agent` repo
4. Railway auto-detects and starts building

### 4.3 Add Environment Variables
In Railway dashboard → your project → **Variables** tab, add all of these:

```
GOOGLE_CLIENT_ID          = your_client_id
GOOGLE_CLIENT_SECRET      = your_client_secret
GOOGLE_REDIRECT_URI       = https://yourapp.up.railway.app/auth/callback
TELEGRAM_BOT_TOKEN        = your_bot_token
TELEGRAM_CHAT_ID          = your_chat_id
GROQ_API_KEY              = your_groq_key
SUPABASE_URL              = https://xxx.supabase.co
SUPABASE_KEY              = your_service_role_key
APP_BASE_URL              = https://yourapp.up.railway.app
SECRET_KEY                = any_random_string
POLL_INTERVAL             = 30
```

### 4.4 Get your Railway URL
1. Railway dashboard → your project → **Settings** tab
2. Under **Domains** → copy the URL (e.g. `https://gmail-ai-agent-production.up.railway.app`)
3. Go back to Google Cloud → update the OAuth redirect URI with this exact URL + `/auth/callback`

---

## STEP 5 — Authenticate Gmail

1. Open browser → go to:
   ```
   https://yourapp.up.railway.app/auth/login
   ```
2. Sign in with your Gmail account
3. Grant all permissions
4. You'll see **"Gmail Connected!"** green page
5. Done — the agent starts monitoring immediately

---

## STEP 6 — Test It

Send yourself a test email with subject like:
```
Interview Invitation - Software Engineer Role
```

Within **30 seconds** you'll get a Telegram message like:

```
🚨 IMPORTANT EMAIL
────────────────────────────
📂 Category: Interview
📨 From: HR Team
📝 Subject: Interview Invitation
📋 Summary: You have been shortlisted...
✅ Action Required
🎯 Score: 95/100
⚡ Urgency: HIGH
```

---

## Telegram Commands

```
/inbox          → Last 10 important emails
/search resume  → Search by keyword
/summarize      → Last 24 hours
/stats          → Processing stats
/help           → All commands
```

## Send Emails via Telegram

Just type:
```
Send email to hr@company.com
Subject: Interview Confirmation
I confirm my availability for the interview tomorrow at 10 AM.
```

---

## Troubleshooting

**Agent not alerting?**
- Check Railway logs (Deployments → View Logs)
- Verify all env variables are set correctly
- Re-authenticate at `/auth/login`

**OAuth error?**
- Make sure the redirect URI in Google Cloud matches Railway URL exactly
- Make sure your Gmail is added as a Test User in OAuth consent screen

**Railway sleeping?**
- Railway free tier does NOT sleep (unlike Render)
- If you see issues, check the Deployments tab for errors
