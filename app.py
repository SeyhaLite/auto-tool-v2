import asyncio
import logging
from flask import Flask, request
from telegram import Update

from bot.core.config import BOT_TOKEN, WEBHOOK_URL, ADMIN_ID
from bot.main import create_application # We will create this file next

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)

# Initialize the Telegram bot application
try:
    ptb_app = create_application()
    logger.info("Telegram Application created successfully.")
except Exception as e:
    logger.critical(f"Failed to create Telegram Application: {e}", exc_info=True)
    ptb_app = None

@app.route("/")
def index():
    """A simple health check page for Render."""
    if ptb_app:
        return "Bot is running! Visit /setup to initialize."
    return "Bot is NOT initialized. Check logs.", 500

@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def webhook():
    """This is the main webhook endpoint that Telegram will send updates to."""
    if not ptb_app:
        logger.error("Webhook received, but Bot Application is not initialized.")
        return "Error: Bot not configured", 500
        
    async def process_update():
        try:
            update_json = request.get_json(force=True)
            update = Update.de_json(update_json, ptb_app.bot)
            await ptb_app.process_update(update)
        except Exception as e:
            logger.error(f"Error processing update: {e}", exc_info=True)
    
    # Run the update processing in an async task
    asyncio.run(process_update())
    return "ok", 200

@app.route("/setup", methods=['GET'])
def setup_bot():
    """
    A setup page to set the webhook.
    Run this *once* after deploying by visiting:
    https://your-app-name.onrender.com/setup
    """
    if not ptb_app:
        return "Bot Application is not initialized. Check logs.", 500
        
    if not WEBHOOK_URL or "YOUR_RENDER_WEB_SERVICE_URL" in WEBHOOK_URL:
        return ("Error: WEBHOOK_URL is not set correctly in bot/core/config.py. "
                "Please edit it with your Render service URL and redeploy."), 400

    async def setup_and_notify():
        try:
            # The full URL Telegram will send updates to
            url = f"{WEBHOOK_URL.rstrip('/')}/{BOT_TOKEN}"
            
            # Set the webhook
            await ptb_app.bot.set_webhook(url=url, allowed_updates=Update.ALL_TYPES)
            
            # Notify admin
            await ptb_app.bot.send_message(
                chat_id=ADMIN_ID,
                text=f"✅ Bot successfully deployed!\nWebhook set to:\n{url}\n\nBot is ready!"
            )
            logger.info(f"Webhook set to {url}")
            return f"Webhook set successfully to {url}. Admin has been notified."
        except Exception as e:
            logger.error(f"Error setting webhook: {e}", exc_info=True)
            return f"Error setting webhook: {e}", 500

    # Run the async setup function
    return asyncio.run(setup_and_notify())

# This block is used if you run `python app.py` locally
if __name__ == "__main__":
    logger.warning("Running app.py directly is for local testing only. Use Gunicorn on Render.")
    app.run(debug=True, port=8080)
