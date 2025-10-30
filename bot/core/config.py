import logging

# WARNING: This file contains sensitive information.
# Keep it safe and do not share it publicly.

# --- Telegram Bot ---
# Your Bot Token from BotFather
BOT_TOKEN = "7441608459:AAGSfpkiLvJFSsr6ubYxu0HoLJsXbTbQUYM"

# Your personal Telegram User ID
ADMIN_ID = 7313962889

# --- Database (PostgreSQL) ---
# Get this from your Render PostgreSQL "External Database URL"
# IMPORTANT: Replace the placeholder below
DATABASE_URL = "postgresql://db_group:NtfUHb8YHm4Mo3mpsE3w9HZfx6mXhWJA@dpg-d41bpl8dl3ps73d9und0-a/db_group"

# --- Webhook (Render Web Service) ---
# Your Render Web Service URL (e.g., "https://your-bot-name.onrender.com")
# IMPORTANT: Replace the placeholder below
WEBHOOK_URL = "https://auto-forward-tg-tool.onrender.com"


# --- Validation ---
if "YOUR_POSTGRES_EXTERNAL_DATABASE_URL_HERE" in DATABASE_URL:
    logging.critical("DATABASE_URL is not set in bot/core/config.py")
    # This will cause the bot to crash, which is intentional
    # You MUST set the database URL
    
if "YOUR_RENDER_WEB_SERVICE_URL_HERE" in WEBHOOK_URL:
    logging.warning("WEBHOOK_URL is not set in bot/core/config.py. "
                    "The /setup endpoint will not work until this is set.")
