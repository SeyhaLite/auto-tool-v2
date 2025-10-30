import logging
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from ..core.database import get_all_active_forward_settings, update_setting_last_processed_id
from .helpers import _send_message_content

logger = logging.getLogger(__name__)

async def handle_new_post(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    This function is triggered by the MessageHandler for new channel posts.
    It checks all 'new_messages' tasks and forwards the post if it matches.
    """
    if not update.channel_post:
        return
        
    message = update.channel_post
    source_id = message.chat_id
    message_id = message.message_id

    # Get all active settings
    all_settings = get_all_active_forward_settings()
    
    # Find settings that match this source channel and are 'new_messages' type
    matching_settings = [
        s for s in all_settings 
        if s['source_channel_id'] == source_id and s['task_type'] == 'new_messages'
    ]

    if not matching_settings:
        return

    logger.info(f"New post {message_id} in {source_id}. Found {len(matching_settings)} matching tasks.")

    for setting in matching_settings:
        try:
            logger.info(f"Processing task {setting['id']}: Forwarding {message_id} from {source_id} to {setting['target_channel_id']}")
            
            await _send_message_content(
                context,
                chat_id=setting['target_channel_id'],
                message=message,
                custom_caption=setting['custom_caption'],
                remove_original_caption=setting['remove_tags_caption']
            )
            
            # Update the last processed ID for this task
            update_setting_last_processed_id(setting['id'], message_id)
            
        except Exception as e:
            logger.error(f"Failed to process task {setting['id']} for message {message_id}: {e}")
            # Notify the user who set up the task
            await context.bot.send_message(
                chat_id=setting['user_id'],
                text=f"⚠️ Task #{setting['id']} បានបរាជ័យក្នុងការ Forward សារ ID <code>{message_id}</code> ពី <code>{source_id}</code>។\nError: {e}",
                parse_mode=ParseMode.HTML
            )
