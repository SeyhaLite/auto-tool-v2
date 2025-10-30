import logging
from telegram import Update, ForceReply, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
from telegram.error import BadRequest

from ..core.config import ADMIN_ID

logger = logging.getLogger(__name__)

async def _send_message_content(context: ContextTypes.DEFAULT_TYPE, chat_id: int, message, custom_caption: str = None, remove_original_caption: bool = True):
    """
    Sends various message types (text, photo, video, document) with custom caption logic.
    Effectively hides sender and original caption by re-sending.
    """
    effective_caption = ""
    original_caption = message.caption or ""
    original_text = message.text or ""

    if not remove_original_caption:
        effective_caption = original_caption
    
    if custom_caption:
        if effective_caption:
            effective_caption += "\n" + custom_caption
        else:
            effective_caption = custom_caption

    effective_caption = effective_caption if effective_caption else None

    try:
        if message.photo:
            await context.bot.send_photo(
                chat_id=chat_id,
                photo=message.photo[-1].file_id,
                caption=effective_caption,
                parse_mode=ParseMode.HTML if effective_caption else None
            )
        elif message.video:
            await context.bot.send_video(
                chat_id=chat_id,
                video=message.video.file_id,
                caption=effective_caption,
                parse_mode=ParseMode.HTML if effective_caption else None
            )
        elif message.document:
            await context.bot.send_document(
                chat_id=chat_id,
                document=message.document.file_id,
                caption=effective_caption,
                parse_mode=ParseMode.HTML if effective_caption else None
            )
        elif message.text:
            text_to_send = ""
            if not remove_original_caption:
                text_to_send = original_text
            
            if custom_caption:
                if text_to_send:
                    text_to_send += "\n" + custom_caption
                else:
                    text_to_send = custom_caption
            
            if not text_to_send and not custom_caption:
                 text_to_send = original_text if not remove_original_caption else None

            if text_to_send:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=text_to_send,
                    parse_mode=ParseMode.HTML
                )
        else:
            logger.warning(f"Unsupported message type for forwarding: {message.message_id}")
            return False
        return True
    except Exception as e:
        logger.error(f"Failed to send message content to {chat_id}: {e}")
        if "chat not found" in str(e):
             await context.bot.send_message(ADMIN_ID, f"⚠️ Error: Bot មិនអាចផ្ញើសារទៅ Target Channel <code>{chat_id}</code> បានទេ។ សូមប្រាកដថា Bot ជា Admin។", parse_mode=ParseMode.HTML)
        return False

async def _send_message_content_by_id(context: ContextTypes.DEFAULT_TYPE, setting: dict):
    """
    Fetches a message by ID and sends it using _send_message_content.
    This is used for ID Range tasks.
    """
    target_id = setting['target_channel_id']
    source_id = setting['source_channel_id']
    message_id = setting['current_message_id']
    custom_caption = setting['custom_caption']
    remove_tags = setting['remove_tags_caption']
    
    try:
        # We must forward the message (e.g., to admin) to get the message object
        temp_forward_message = await context.bot.forward_message(
            chat_id=ADMIN_ID, # Forward to admin
            from_chat_id=source_id,
            message_id=message_id
        )

        success = await _send_message_content(
            context,
            target_id,
            temp_forward_message, # Use the forwarded message object
            custom_caption,
            remove_tags
        )

        # Delete the temporary message from admin's chat
        try:
            await context.bot.delete_message(
                chat_id=ADMIN_ID,
                message_id=temp_forward_message.message_id
            )
        except Exception as e:
            logger.warning(f"Failed to delete temp forward message from admin: {e}")

        return success
    
    except BadRequest as e:
        error_message = str(e)
        if "message to forward not found" in error_message or "can't be forwarded" in error_message:
            logger.warning(f"Task {setting['id']}: Message {message_id} in {source_id} not found or can't be forwarded. Skipping.")
            return 'not_found' # Special return to skip this ID
        
        logger.error(f"Critical BadRequest in _send_message_content_by_id (Task {setting['id']}): {e}")
        if "chat not found" in error_message:
             await context.bot.send_message(ADMIN_ID, f"⚠️ Task {setting['id']} Error: Bot មិនអាចអានពី Source Channel <code>{source_id}</code> បានទេ។ សូមប្រាកដថា Bot ជា Admin។", parse_mode=ParseMode.HTML)
        return False

    except Exception as e:
        logger.error(f"Error in _send_message_content_by_id (Task {setting['id']}): {e}")
        if "message to forward not found" in str(e):
            logger.warning(f"Task {setting['id']}: Message {message_id} in {source_id} not found. Skipping.")
            return 'not_found'
        if "chat not found" in str(e):
             await context.bot.send_message(ADMIN_ID, f"⚠️ Task {setting['id']} Error: Bot មិនអាចអានពី Source Channel <code>{source_id}</code> បានទេ។ សូមប្រាកដថា Bot ជា Admin។", parse_mode=ParseMode.HTML)
        return False

async def validate_channel_id(update: Update, context: ContextTypes.DEFAULT_TYPE, next_state: int):
    """Helper to validate channel ID and move to next state."""
    try:
        channel_id = int(update.message.text.strip())
        if not (channel_id < -1000000000 or (channel_id < 0 and channel_id > -1000000000)):
             if channel_id > 0:
                 await update.message.reply_html("<b>⚠️ ID មិនត្រឹមត្រូវទេ។</b> ID សម្រាប់ Channel/Group ត្រូវតែជាលេខអវិជ្ជមាន (ឧ: <code>-100123...</code>)។")
                 return
        
        try:
            # Check if bot can get chat info
            chat = await context.bot.get_chat(channel_id)
            if chat.type not in ['channel', 'supergroup']:
                await update.message.reply_html("<b>⚠️ ID នេះមិនមែនជា Channel ឬ Group ទេ។</b>")
                return
        except Exception as e:
            logger.error(f"Error getting chat info for {channel_id}: {e}")
            await update.message.reply_html(f"<b>⚠️ មិនអាចផ្ទៀងផ្ទាត់ ID Channel/Group បានទេ។</b> សូមប្រាកដថា ID ត្រឹមត្រូវ ហើយ Bot ជាសមាជិក ឬ Admin។ (Error: {e})")
            return
        
        return channel_id, next_state

    except ValueError:
        await update.message.reply_html("<b>⚠️ ID Channel មិនត្រឹមត្រូវទេ។</b> សូមផ្ញើ ID ជាលេខ។")
        return None, None
    except Exception as e:
        logger.error(f"Error in validate_channel_id: {e}")
        await update.message.reply_html(f"<b>⚠️ មានបញ្ហា៖</b> {e}")
        return None, None
