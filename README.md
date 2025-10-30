# Telegram Forwarder Bot (Webhook Version)

This bot is designed to be deployed on a web service like Render. It uses a webhook to receive updates from Telegram and a PostgreSQL database to store data.

## 🚀 Deployment on Render

1.  **Create PostgreSQL Database on Render:**
    * Go to your Render Dashboard.
    * Click "New" -> "PostgreSQL".
    * Choose the "Free" plan.
    * After it's created, go to the "Connect" tab and find the **External Database URL**. It will look like `postgresql://user:password@host/database`.

2.  **Edit Your Config File:**
    * Open the file `bot/core/config.py` in your code editor.
    * Paste the **External Database URL** into the `DATABASE_URL` variable, replacing the placeholder.

3.  **Create Web Service on Render:**
    * Go to your Render Dashboard.
    * Click "New" -> "Web Service".
    * Connect the GitHub repository containing all these bot files.
    * Render will detect `render.yaml`. Give your service a unique name (e.g., `my-telegram-bot`). This name will be part of your URL.
    * Click "Create Web Service".

4.  **Set the Webhook URL:**
    * Wait for your service to deploy. It will have a URL like `https://my-telegram-bot.onrender.com`.
    * Go back to `bot/core/config.py` in your code editor.
    * Change the `WEBHOOK_URL` variable to your service's URL:
        ```python
        WEBHOOK_URL = "[https://my-telegram-bot.onrender.com](https://my-telegram-bot.onrender.com)" 
        ```
    * Commit and push this change to GitHub. Render will automatically redeploy with the new URL.

5.  **Initialize the Bot (One-Time Setup):**
    * Once the new version is deployed, open a new browser tab.
    * Go to your bot's URL with `/setup` at the end:
        `https://my-telegram-bot.onrender.com/setup`
    * You should see a message like "Webhook set successfully...".
    * Check your bot on Telegram. You (as the Admin) should have received a confirmation message.

Your bot is now live and running!
