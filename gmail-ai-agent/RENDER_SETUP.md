# 🚀 Render.com Deployment & Keep-Alive Guide

This guide walks you through migrating and deploying your **Gmail AI Agent** from Railway to **Render.com** free hosting tier. It also shows you how to bypass the Render 15-minute inactivity shutdown using UptimeRobot so your email poller runs 24/7.

---

## 📋 Prerequisites

Before starting, ensure you have:
1. A **GitHub** account with your code pushed.
2. A **Supabase** database with the database schema initialized.
3. A **Groq API Key** and a **Telegram Bot** token.
4. A **Google Cloud Project** with the Gmail API enabled.

---

## 🛠️ Step 1: Deploy on Render

Render supports **Blueprints** (`render.yaml`), which pre-configure your web app environment variables automatically.

1. Go to the [Render Dashboard](https://dashboard.render.com/) and sign up.
2. Click **New +** (top right) and select **Blueprint**.
3. Connect your GitHub repository.
4. Render will scan `render.yaml` and prompt you to name the service group (e.g., `gmail-ai-agent-group`).
5. Fill in the required environment variables:
   * `GOOGLE_CLIENT_ID`
   * `GOOGLE_CLIENT_SECRET`
   * `TELEGRAM_BOT_TOKEN`
   * `TELEGRAM_CHAT_ID`
   * `GROQ_API_KEY`
   * `SUPABASE_URL`
   * `SUPABASE_KEY`
   * `SECRET_KEY` (Any secure random string)
   * `APP_BASE_URL` (Enter `https://<your-service-name>.onrender.com` once you know the URL, or leave blank and update later)
   * `GOOGLE_REDIRECT_URI` (Enter `https://<your-service-name>.onrender.com/auth/callback`)
6. Click **Approve** to build and deploy.

---

## 🔑 Step 2: Update Google Cloud Redirect URI

Render will assign your web service a URL (e.g., `https://gmail-ai-agent-a78b.onrender.com`).

1. Copy your Render URL.
2. Go to the [Google Cloud Console](https://console.cloud.google.com/).
3. Navigate to **APIs & Services** ➡️ **Credentials**.
4. Click edit on your OAuth 2.0 Client ID.
5. Under **Authorized redirect URIs**, add your new redirect endpoint:
   ```text
   https://gmail-ai-agent-a78b.onrender.com/auth/callback
   ```
6. Save the changes.
7. Go back to Render Dashboard ➡️ your Web Service ➡️ **Environment** tab, and verify that `GOOGLE_REDIRECT_URI` and `APP_BASE_URL` match your Render domain URL.

---

## ⏰ Step 3: Prevent Inactivity Sleep (UptimeRobot)

Render's free tier automatically suspends (spins down) the container if it does not receive any web traffic for **15 minutes**. Since our agent relies on a background poller, we must prevent it from going to sleep.

We use **UptimeRobot** to periodically ping the newly added `/ping` route:

1. Sign up for a free account at [UptimeRobot](https://uptimerobot.com/).
2. Click **Add New Monitor**.
3. Configure the monitor details:
   * **Monitor Type**: `HTTP(s)`
   * **Friendly Name**: `Gmail AI Agent Keep-Alive`
   * **URL (or IP)**: `https://<your-render-app-name>.onrender.com/ping`
   * **Monitoring Interval**: Every `5 minutes` (or `10 minutes`)
4. Click **Create Monitor**.

Now, UptimeRobot will ping `/ping` every 5 minutes, preventing Render from spinning down the service. Your background thread will continue polling Gmail 24/7!

---

## 🧪 Step 4: Authenticate & Test

1. Visit the OAuth connection link:
   ```text
   https://<your-render-app-name>.onrender.com/auth/login
   ```
2. Authenticate with your Gmail account.
3. Once redirected to the **"Gmail Connected!"** success page, verify that the health and ping status endpoints respond correctly:
   * `https://<your-render-app-name>.onrender.com/health`
   * `https://<your-render-app-name>.onrender.com/ping`
4. Type `/stats` or `/help` in Telegram to check the bot's responsiveness.
