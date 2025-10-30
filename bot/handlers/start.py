import logging
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ContextTypes, ConversationHandler
from telegram.constants import ParseMode

from ..core.database import get_user, add_user, get_user_forward_settings
from ..core.config import ADMIN_ID

logger = logging.getLogger(__name__)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Sends a welcome message and registers the user."""
    user = update.effective_user
    is_admin = (user.id == ADMIN_ID)

    # Add user to DB if not exists
    existing_user = get_user(user.id)
    if not existing_user:
        add_user(user.id, user.username, user.first_name, user.last_name, is_admin)
        logger.info(f"New user registered: {user.id} ({user.username})")
        
        # Notify admin about new user
        if user.id != ADMIN_ID:
            user_link = f"<a href='tg://user?id={user.id}'>{user.first_name or 'User'}</a>"
            admin_message = (
                f"📢 <b>User ថ្មីបានចូលរួម</b>\n\n"
                f"<b>Name:</b> {user_link}\n"
                f"<b>ID:</b> <code>{user.id}</code>\n"
                f"<b>Username:</b> @{user.username or 'N/A'}"
            )
            try:
                await context.bot.send_message(chat_id=ADMIN_ID, text=admin_message, parse_mode=ParseMode.HTML)
            except Exception as e:
                logger.error(f"Failed to send new user notification to admin: {e}")

    elif existing_user['is_banned']:
        banned_until = existing_user['banned_until']
        if banned_until and banned_until > datetime.now():
            await update.message.reply_html(f"<b>🚫 សូមអភ័យទោស!</b> អ្នកត្រូវបានបិទមិនឱ្យប្រើ Bot នេះបណ្តោះអាសន្នរហូតដល់៖ "
                                            f"<code>{banned_until}</code>។")
            return ConversationHandler.END

    keyboard = [
        [KeyboardButton("ការកំណត់ Bot ⚙️"), KeyboardButton("ស្ថានភាព Bot 📊")],
        [KeyboardButton("សាកល្បង Forward 🧪"), KeyboardButton("ព័ត៌មាន Profile 👤")]
    ]
    if is_admin:
        keyboard.append([KeyboardButton("ផ្ទាំងគ្រប់គ្រង Admin 👑")])

    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)

    message_text = (
        f"<b>👋 សួស្តី {user.mention_html()}!</b>\n"
        "ខ្ញុំគឺជា Bot សម្រាប់ជួយអ្នក Auto Forward សារពី Channel មួយទៅ Channel មួយទៀត។\n\n"
        "សូមជ្រើសរើសមុខងារខាងក្រោម៖"
    )

    if update.callback_query:
        await update.callback_query.answer()
        # We must delete the old message and send a new one
        try:
            await update.callback_query.message.delete()
        except Exception as e:
            logger.warning(f"Could not delete message on start: {e}")
            
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=message_text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML
        )
    elif update.message:
        await update.message.reply_html(
            text=message_text,
            reply_markup=reply_markup,
        )
    return ConversationHandler.END

async def back_to_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Returns to the main menu."""
    await start(update, context)
    return ConversationHandler.END


async def show_profile(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Shows user's profile information."""
    user = update.effective_user
    user_data = get_user(user.id)
    if user_data:
        is_admin_text = "បាទ/ចាស ✅" if user_data['is_admin'] else "ទេ ❌"
        is_banned_text = "បាទ/ចាស ⛔" if user_data['is_banned'] else "ទេ ✅"
        banned_until_text = user_data['banned_until'] if user_data['banned_until'] else "មិនមាន"
        joined_at_text = user_data['joined_at'].strftime('%Y-%m-%d %H:%M:%S') if user_data['joined_at'] else "N/A"
        
        await update.message.reply_html(
            f"<b>👤 ព័ត៌មាន Profile របស់អ្នក</b>\n"
            f"<b>➡️ ID អ្នកប្រើប្រាស់:</b> <code>{user.id}</code>\n"
            f"<b>➡️ ឈ្មោះ:</b> {user.first_name} {user_data['last_name'] or ''}\n"
            f"<b>➡️ Username:</b> @{user_data['username'] or 'N/A'}\n"
            f"<b>➡️ បានចូលរួម:</b> {joined_at_text}\n"
            f"<b>➡️ ជា Admin:</b> {is_admin_text}\n"
            f"<b>➡️ ត្រូវបានហាមឃាត់:</b> {is_banned_text}\n"
            f"<b>➡️ ហាមឃាត់រហូតដល់:</b> {banned_until_text}"
        )
    else:
        await update.message.reply_text("🔎 រកមិនឃើញព័ត៌មាន Profile របស់អ្នកទេ។ សូមសាកល្បង /start ម្តងទៀត។")

async def show_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Shows bot status and user's active forward settings."""
    user = update.effective_user
    settings = get_user_forward_settings(user.id)

    status_message = "<b>📊 ស្ថានភាព Bot</b>\n\n"
    if not settings:
        status_message += "អ្នកមិនទាន់បានកំណត់ Task ណាមួយនៅឡើយទេ។\n"
        status_message += "សូមចូលទៅកាន់ 'ការកំណត់ Bot ⚙️' ដើម្បីចាប់ផ្តើម។"
    else:
        status_message += "<b>➡️ Tasks របស់អ្នក:</b>\n"
        for i, setting in enumerate(settings):
            task_type = setting.get('task_type', 'new_messages')
            
            status_message += f"\n<b>✨ Task #{setting['id']}</b> ({'សកម្ម ✅' if setting['is_active'] else 'ផ្អាក ⏸️'})\n"
            status_message += f"  <b>- ប្រភេទ:</b> {'សារថ្មីៗ' if task_type == 'new_messages' else 'តាម ID Range'}\n"
            status_message += f"  <b>- Source:</b> <code>{setting['source_channel_id']}</code>\n"
            status_message += f"  <b>- Target:</b> <code>{setting['target_channel_id']}</code>\n"
            status_message += f"  <b>- Interval:</b> {setting.get('interval_seconds', 'N/A')} វិនាទី\n"
            status_message += f"  <b>- Caption:</b> {setting['custom_caption'] or 'គ្មាន'}\n"
            status_message += f"  <b>- លុប Caption ដើម:</b> {'បាទ/ចាស' if setting['remove_tags_caption'] else 'ទេ'}\n"
            
            if task_type == 'id_range':
                status_message += f"  <b>- ID Range:</b> <code>{setting.get('start_message_id', 0)}</code> ដល់ <code>{setting.get('end_message_id', 0)}</code>\n"
                status_message += f"  <b>- ID បច្ចុប្បន្ន:</b> <code>{setting.get('current_message_id', 0)}</code>\n"
                status_message += f"  <b>- ដំណើរការរាល់:</b> {setting.get('forward_every_n_posts', 1)} post\n"
            else:
                status_message += f"  <b>- សារចុងក្រោយ:</b> <code>{setting.get('last_processed_message_id', 0)}</code>\n"

    await update.message.reply_html(status_message)
