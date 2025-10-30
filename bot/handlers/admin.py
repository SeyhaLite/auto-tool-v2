import logging
import re
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ConversationHandler,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters
)
from telegram.constants import ParseMode

from ..core.database import (
    get_total_users,
    get_all_users_ids,
    get_user,
    update_user_ban_status
)
from ..core.config import ADMIN_ID
from .start import start, back_to_main_menu

logger = logging.getLogger(__name__)

# Conversation states
(ADMIN_PANEL_MENU, BROADCAST_MESSAGE, 
 BROADCAST_CONFIRM, MANAGE_USER_ID, MANAGE_USER_ACTION, MANAGE_USER_TIME, 
 ADMIN_BROADCAST_PHOTO_TEXT, ADMIN_BROADCAST_VIDEO_TEXT, 
 BROADCAST_PROMPT_MESSAGE_ID) = range(9)


# --- Admin Panel Functions ---

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Shows the admin panel menu."""
    user = update.effective_user
    if user.id != ADMIN_ID:
        if update.message:
            await update.message.reply_text("🚫 អ្នកមិនមានសិទ្ធិចូលប្រើផ្ទាំងគ្រប់គ្រង Admin ទេ។")
        else:
            await update.callback_query.answer("🚫 អ្នកមិនមានសិទ្ធិចូលប្រើផ្ទាំងគ្រប់គ្រង Admin ទេ។", show_alert=True)
        return ConversationHandler.END

    keyboard = [
        [InlineKeyboardButton("📊 មើលចំនួន User សរុប", callback_data="admin_total_users")],
        [InlineKeyboardButton("📢 ផ្សាយសារទៅ User ទាំងអស់", callback_data="admin_broadcast_menu")],
        [InlineKeyboardButton("🚫 គ្រប់គ្រង User (Ban/Unban/Stop)", callback_data="admin_manage_user")],
        [InlineKeyboardButton("⬅️ ត្រលប់ក្រោយ", callback_data="back_to_main")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    total_users = get_total_users()
    message_text = f"<b>👑 ផ្ទាំងគ្រប់គ្រង Admin</b>\n\n<b>User សរុប:</b> <code>{total_users}</code> នាក់\n\nសូមជ្រើសរើសមុខងារគ្រប់គ្រង៖"
    
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.message.edit_text(
            text=message_text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML
        )
    else:
        await update.message.reply_html(
            text=message_text,
            reply_markup=reply_markup
        )
    return ADMIN_PANEL_MENU

async def admin_total_users(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Refreshes the admin panel showing total users."""
    await query.answer()
    # The total users is already shown in the main admin panel
    # This just acts as a refresh
    return await admin_panel(update, context)


async def admin_broadcast_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Shows broadcast options."""
    query = update.callback_query
    await query.answer()

    keyboard = [
        [InlineKeyboardButton("📝 ផ្ញើសារធម្មតា (Text)", callback_data="broadcast_text")],
        [InlineKeyboardButton("📸 ផ្ញើជាមួយរូបភាព", callback_data="broadcast_photo")],
        [InlineKeyboardButton("🎥 ផ្ញើជាមួយវីដេអូ", callback_data="broadcast_video")],
        [InlineKeyboardButton("➡️ Forward សារដែលមានស្រាប់", callback_data="broadcast_forward_post")],
        [InlineKeyboardButton("⬅️ ត្រលប់ក្រោយ", callback_data="back_to_admin_panel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        """<b>📢 ផ្សាយសារទៅកាន់ User ទាំងអស់</b>

សូមជ្រើសរើសប្រភេទសារដែលអ្នកចង់ផ្សាយ៖""",
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML
    )
    return BROADCAST_MESSAGE

async def broadcast_text_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Prompts admin for text message to broadcast."""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        """<b>📝 ផ្ញើសារធម្មតា (Text)</b>

<b>➡️ សូមផ្ញើសារដែលអ្នកចង់ផ្សាយទៅកាន់ User ទាំងអស់។</b>
អ្នកអាចប្រើ HTML tags (Bold, Italic, Link) ។""",
        parse_mode=ParseMode.HTML
    )
    context.user_data['broadcast_type'] = 'text'
    return BROADCAST_CONFIRM

async def broadcast_photo_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Prompts admin for photo and optional caption to broadcast."""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        """<b>📸 ផ្ញើជាមួយរូបភាព</b>

<b>➡️ សូមផ្ញើរូបភាពដែលអ្នកចង់ផ្សាយ។</b> អ្នកក៏អាចបន្ថែម Caption ផងដែរ។""",
        parse_mode=ParseMode.HTML
    )
    context.user_data['broadcast_type'] = 'photo'
    return ADMIN_BROADCAST_PHOTO_TEXT

async def broadcast_video_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Prompts admin for video and optional caption to broadcast."""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        """<b>🎥 ផ្ញើជាមួយវីដេអូ</b>

<b>➡️ សូមផ្ញើវីដេអូដែលអ្នកចង់ផ្សាយ។</b> អ្នកក៏អាចបន្ថែម Caption ផងដែរ។""",
        parse_mode=ParseMode.HTML
    )
    context.user_data['broadcast_type'] = 'video'
    return ADMIN_BROADCAST_VIDEO_TEXT

async def broadcast_forward_post_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Prompts admin for message ID to forward as broadcast."""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        """<b>➡️ Forward សារដែលមានស្រាប់</b>

<b>➡️ សូម Forward សារណាមួយពី Channel ឬ Group ផ្សេងមកកាន់ Bot នេះ។</b>
Bot នឹង Forward សារនោះទៅកាន់ User ទាំងអស់។""",
        parse_mode=ParseMode.HTML
    )
    context.user_data['broadcast_type'] = 'forward'
    return BROADCAST_CONFIRM # Use BROADCAST_CONFIRM to process the forwarded message

async def handle_broadcast_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles various types of broadcast messages (text, photo, video, forwarded)."""
    broadcast_type = context.user_data.get('broadcast_type')

    if broadcast_type == 'text':
        message_to_broadcast = update.message.text
        context.user_data['broadcast_text'] = message_to_broadcast
    elif broadcast_type == 'photo':
        if update.message.photo:
            context.user_data['broadcast_file_id'] = update.message.photo[-1].file_id
            context.user_data['broadcast_caption'] = update.message.caption
            message_to_broadcast = "photo" # Placeholder
        else:
            await update.message.reply_html("<b>⚠️ សូមផ្ញើរូបភាព។</b>")
            return ADMIN_BROADCAST_PHOTO_TEXT
    elif broadcast_type == 'video':
        if update.message.video:
            context.user_data['broadcast_file_id'] = update.message.video.file_id
            context.user_data['broadcast_caption'] = update.message.caption
            message_to_broadcast = "video" # Placeholder
        else:
            await update.message.reply_html("<b>⚠️ សូមផ្ញើវីដេអូ។</b>")
            return ADMIN_BROADCAST_VIDEO_TEXT
    elif broadcast_type == 'forward':
        if update.message.forward_from_chat and update.message.forward_from_message_id:
            context.user_data['forward_from_chat_id'] = update.message.forward_from_chat.id
            context.user_data['forward_message_id'] = update.message.forward_from_message_id
            message_to_broadcast = "forward" # Placeholder
        else:
            await update.message.reply_html("<b>⚠️ សូម Forward សារ។</b>")
            return BROADCAST_CONFIRM
    else:
        await update.message.reply_html("<b>⚠️ ប្រភេទសារផ្សាយមិនស្គាល់។</b>")
        return ConversationHandler.END

    keyboard = [
        [InlineKeyboardButton("✅ បាទ/ចាស ផ្សាយឥឡូវនេះ", callback_data="confirm_broadcast_yes")],
        [InlineKeyboardButton("❌ ទេ បោះបង់", callback_data="confirm_broadcast_no")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    confirm_text = ""
    if broadcast_type == 'text':
        confirm_text = f"<b>សារដែលអ្នកនឹងផ្សាយ៖</b>\n\n{message_to_broadcast}"
    elif broadcast_type == 'photo':
        confirm_text = f"<b>អ្នកនឹងផ្សាយរូបភាពនេះ។</b>\nCaption: {context.user_data.get('broadcast_caption') or 'គ្មាន'}"
    elif broadcast_type == 'video':
        confirm_text = f"<b>អ្នកនឹងផ្សាយវីដេអូនេះ។</b>\nCaption: {context.user_data.get('broadcast_caption') or 'គ្មាន'}"
    elif broadcast_type == 'forward':
        confirm_text = f"<b>អ្នកនឹង Forward សារ ID <code>{context.user_data.get('forward_message_id')}</code> ពី Channel <code>{context.user_data.get('forward_from_chat_id')}</code> ។</b>"

    await update.message.reply_html(
        f"""<b>📢 ផ្ទៀងផ្ទាត់ការផ្សាយសារ</b>

{confirm_text}

<b>តើអ្នកពិតជាចង់ផ្សាយសារនេះទៅកាន់ User ទាំងអស់មែនទេ?</b>""",
        reply_markup=reply_markup
    )
    return BROADCAST_CONFIRM

async def execute_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Executes the broadcast based on admin's confirmation."""
    query = update.callback_query
    await query.answer()

    if query.data == "confirm_broadcast_no":
        await query.edit_message_text("❌ ការផ្សាយសារត្រូវបានបោះបង់។")
        context.user_data.clear()
        await admin_panel(update, context)
        return ConversationHandler.END

    broadcast_type = context.user_data.get('broadcast_type')
    users_to_broadcast = get_all_users_ids()
    success_count = 0
    fail_count = 0

    await query.edit_message_text(f"⏳ កំពុងផ្សាយសារទៅកាន់ User <code>{len(users_to_broadcast)}</code> នាក់... សូមរង់ចាំ។")

    for user_id in users_to_broadcast:
        try:
            if broadcast_type == 'text':
                await context.bot.send_message(chat_id=user_id, text=context.user_data.get('broadcast_text'), parse_mode=ParseMode.HTML)
            elif broadcast_type == 'photo':
                await context.bot.send_photo(chat_id=user_id, photo=context.user_data.get('broadcast_file_id'), caption=context.user_data.get('broadcast_caption'), parse_mode=ParseMode.HTML)
            elif broadcast_type == 'video':
                await context.bot.send_video(chat_id=user_id, video=context.user_data.get('broadcast_file_id'), caption=context.user_data.get('broadcast_caption'), parse_mode=ParseMode.HTML)
            elif broadcast_type == 'forward':
                await context.bot.forward_message(chat_id=user_id, from_chat_id=context.user_data.get('forward_from_chat_id'), message_id=context.user_data.get('forward_message_id'))
            success_count += 1
        except Exception as e:
            logger.error(f"Failed to broadcast to user {user_id}: {e}")
            fail_count += 1

    await query.edit_message_text(
        f"""✅ ការផ្សាយសារបានបញ្ចប់!
<b>➡️ បានជោគជ័យ:</b> <code>{success_count}</code> នាក់
<b>➡️ បានបរាជ័យ:</b> <code>{fail_count}</code> នាក់""",
        parse_mode=ParseMode.HTML
    )
    context.user_data.clear()
    await admin_panel(update, context)
    return ConversationHandler.END

async def back_to_admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Returns to the admin panel menu."""
    if update.callback_query:
        await update.callback_query.answer()
    return await admin_panel(update, context)


async def admin_manage_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Prompts admin to enter user ID for management."""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        """<b>🚫 គ្រប់គ្រង User (Ban/Unban/Stop)</b>

<b>➡️ សូមផ្ញើ User ID របស់ User ដែលអ្នកចង់គ្រប់គ្រង។</b>""",
        parse_mode=ParseMode.HTML
    )
    return MANAGE_USER_ID

async def admin_select_user_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Allows admin to select action for the given user ID."""
    try:
        user_id_to_manage = int(update.message.text.strip())
        user_data = get_user(user_id_to_manage)
        if not user_data:
            await update.message.reply_html("<b>⚠️ រកមិនឃើញ User ID នេះទេ។</b> សូមបញ្ចូល User ID ត្រឹមត្រូវ។")
            return MANAGE_USER_ID

        context.user_data['user_id_to_manage'] = user_id_to_manage

        is_banned = user_data['is_banned']
        banned_until = user_data['banned_until']

        status_text = "<b>ស្ថានភាពបច្ចុប្បន្ន៖</b> "
        if is_banned:
            if banned_until and banned_until > datetime.now():
                status_text += f"ត្រូវបានបិទរហូតដល់ <code>{banned_until}</code>"
            else:
                status_text += "ត្រូវបានបិទជាអចិន្ត្រៃយ៍"
        else:
            status_text += "មិនត្រូវបានបិទទេ"


        keyboard = [
            [InlineKeyboardButton("⛔ Ban User", callback_data="manage_ban_user")],
            [InlineKeyboardButton("✅ Unban User", callback_data="manage_unban_user")],
            [InlineKeyboardButton("⏳ Stop User មួយរយៈ", callback_data="manage_stop_time")],
            [InlineKeyboardButton("⬅️ ត្រលប់ក្រោយ", callback_data="back_to_admin_panel")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_html(
            f"""<b>⚙️ គ្រប់គ្រង User ID:</b> <code>{user_id_to_manage}</code>
<b>ឈ្មោះ:</b> {user_data['first_name'] or 'N/A'} {user_data['last_name'] or ''}
<b>Username:</b> @{user_data['username'] or 'N/A'}

{status_text}

<b>សូមជ្រើសរើសសកម្មភាព៖</b>""",
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML
        )
        return MANAGE_USER_ACTION
    except ValueError:
        await update.message.reply_html("<b>⚠️ User ID មិនត្រឹមត្រូវទេ។</b> សូមផ្ញើ User ID ដែលជាលេខ។")
        return MANAGE_USER_ID

async def admin_ban_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Bans a user permanently."""
    query = update.callback_query
    await query.answer()

    user_id_to_manage = context.user_data.get('user_id_to_manage')
    if user_id_to_manage == ADMIN_ID:
        await query.edit_message_text("🚫 អ្នកមិនអាច Ban ខ្លួនឯងបានទេ។")
        context.user_data.clear()
        await back_to_admin_panel(update, context)
        return ConversationHandler.END

    update_user_ban_status(user_id_to_manage, True, None)
    await query.edit_message_text(f"✅ User ID <code>{user_id_to_manage}</code> ត្រូវបាន <b>Ban</b> ដោយជោគជ័យ។", parse_mode=ParseMode.HTML)

    try:
        await context.bot.send_message(chat_id=user_id_to_manage, text="🚫 អ្នកត្រូវបានបិទមិនឱ្យប្រើ Bot នេះដោយ Admin ។")
    except Exception as e:
        logger.warning(f"Could not notify banned user {user_id_to_manage}: {e}")

    context.user_data.clear()
    await back_to_admin_panel(update, context)
    return ConversationHandler.END

async def admin_unban_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Unbans a user."""
    query = update.callback_query
    await query.answer()

    user_id_to_manage = context.user_data.get('user_id_to_manage')
    update_user_ban_status(user_id_to_manage, False, None)
    await query.edit_message_text(f"✅ User ID <code>{user_id_to_manage}</code> ត្រូវបាន <b>Unban</b> ដោយជោគជ័យ។", parse_mode=ParseMode.HTML)

    try:
        await context.bot.send_message(chat_id=user_id_to_manage, text="🎉 អ្នកត្រូវបានអនុញ្ញាតឱ្យប្រើ Bot នេះឡើងវិញហើយ!")
    except Exception as e:
        logger.warning(f"Could not notify unbanned user {user_id_to_manage}: {e}")

    context.user_data.clear()
    await back_to_admin_panel(update, context)
    return ConversationHandler.END

async def admin_stop_user_prompt_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Prompts admin for time to stop (ban temporarily) a user."""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        """<b>⏳ Stop User មួយរយៈ</b>

<b>➡️ សូមបញ្ចូលរយៈពេលដែលអ្នកចង់បិទ User (ជាចំនួននាទី)។</b>
ឧទាហរណ៍: <code>60</code> សម្រាប់ 1 ម៉ោង, <code>1440</code> សម្រាប់ 1 ថ្ងៃ។""",
        parse_mode=ParseMode.HTML
    )
    return MANAGE_USER_TIME

async def admin_set_stop_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Sets a temporary ban for a user."""
    try:
        duration_minutes = int(update.message.text.strip())
        if duration_minutes <= 0:
            await update.message.reply_html("<b>⚠️ រយៈពេលមិនត្រឹមត្រូវទេ។</b>")
            return MANAGE_USER_TIME

        user_id_to_manage = context.user_data.get('user_id_to_manage')
        if user_id_to_manage == ADMIN_ID:
            await update.message.reply_html("🚫 អ្នកមិនអាចកំណត់ Stop Time លើខ្លួនឯងបានទេ។")
            context.user_data.clear()
            await back_to_admin_panel(update, context)
            return ConversationHandler.END

        banned_until = datetime.now() + timedelta(minutes=duration_minutes)
        update_user_ban_status(user_id_to_manage, True, banned_until)

        await update.message.reply_html(
            f"✅ User ID <code>{user_id_to_manage}</code> ត្រូវបានបិទបណ្តោះអាសន្នរហូតដល់៖ "
            f"<code>{banned_until.strftime('%Y-%m-%d %H:%M:%S')}</code>",
            parse_mode=ParseMode.HTML
        )

        try:
            await context.bot.send_message(
                chat_id=user_id_to_manage,
                text=f"🚫 អ្នកត្រូវបានបិទមិនឱ្យប្រើ Bot នេះបណ្តោះអាសន្នរហូតដល់៖ "
                     f"<code>{banned_until.strftime('%Y-%m-%d %H:%M:%S')}</code> ដោយ Admin ។",
                parse_mode=ParseMode.HTML
            )
        except Exception as e:
            logger.warning(f"Could not notify temporarily banned user {user_id_to_manage}: {e}")

        context.user_data.clear()
        await back_to_admin_panel(update, context)
        return ConversationHandler.END
    except ValueError:
        await update.message.reply_html("<b>⚠️ រយៈពេលមិនត្រឹមត្រូវទេ។</b> សូមបញ្ចូលចំនួននាទីជាលេខ។")
        return MANAGE_USER_TIME


def get_admin_conv_handler() -> ConversationHandler:
    """Returns the ConversationHandler for the admin panel."""
    return ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^ផ្ទាំងគ្រប់គ្រង Admin 👑$"), admin_panel),
            CallbackQueryHandler(admin_panel, pattern="^back_to_admin_panel$")
        ],
        states={
            ADMIN_PANEL_MENU: [
                CallbackQueryHandler(admin_total_users, pattern="^admin_total_users$"),
                CallbackQueryHandler(admin_broadcast_menu, pattern="^admin_broadcast_menu$"),
                CallbackQueryHandler(admin_manage_user, pattern="^admin_manage_user$"),
                CallbackQueryHandler(back_to_main_menu, pattern="^back_to_main$"),
            ],
            BROADCAST_MESSAGE: [
                CallbackQueryHandler(broadcast_text_prompt, pattern="^broadcast_text$"),
                CallbackQueryHandler(broadcast_photo_prompt, pattern="^broadcast_photo$"),
                CallbackQueryHandler(broadcast_video_prompt, pattern="^broadcast_video$"),
                CallbackQueryHandler(broadcast_forward_post_prompt, pattern="^broadcast_forward_post$"),
                CallbackQueryHandler(back_to_admin_panel, pattern="^back_to_admin_panel$"),
            ],
            BROADCAST_CONFIRM: [
                MessageHandler(filters.TEXT & ~filters.COMMAND | filters.PHOTO | filters.VIDEO | filters.FORWARDED, handle_broadcast_message),
                CallbackQueryHandler(execute_broadcast, pattern="^confirm_broadcast_(yes|no)$"),
            ],
            ADMIN_BROADCAST_PHOTO_TEXT: [
                MessageHandler(filters.PHOTO | (filters.TEXT & ~filters.COMMAND), handle_broadcast_message),
            ],
            ADMIN_BROADCAST_VIDEO_TEXT: [
                MessageHandler(filters.VIDEO | (filters.TEXT & ~filters.COMMAND), handle_broadcast_message),
            ],
            MANAGE_USER_ID: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_select_user_action),
            ],
            MANAGE_USER_ACTION: [
                CallbackQueryHandler(admin_ban_user, pattern="^manage_ban_user$"),
                CallbackQueryHandler(admin_unban_user, pattern="^manage_unban_user$"),
                CallbackQueryHandler(admin_stop_user_prompt_time, pattern="^manage_stop_time$"),
                CallbackQueryHandler(back_to_admin_panel, pattern="^back_to_admin_panel$"),
            ],
            MANAGE_USER_TIME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_set_stop_time),
            ],
        },
        fallbacks=[CommandHandler("start", start), MessageHandler(filters.Regex("^ផ្ទាំងគ្រប់គ្រង Admin 👑$"), admin_panel)],
        per_message=False
    )
