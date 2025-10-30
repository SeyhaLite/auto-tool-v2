import logging
import re
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

from ..core.database import get_user_forward_settings, get_setting_by_id
from .helpers import _send_message_content_by_id
from .start import start, back_to_main_menu

logger = logging.getLogger(__name__)

# Conversation states
TEST_FORWARD_PROMPT_ID, BROADCAST_PROMPT_MESSAGE_ID = range(2)


async def test_forward_prompt_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Prompts the user to select a setting for test forward."""
    user_id = update.effective_user.id
    settings = get_user_forward_settings(user_id)

    if not settings:
        await update.message.reply_html("អ្នកមិនទាន់មាន Task ណាមួយទេ។ សូមកំណត់វានៅក្នុង 'ការកំណត់ Bot ⚙️'។")
        return ConversationHandler.END

    keyboard = []
    for setting in settings:
        keyboard.append([InlineKeyboardButton(f"➡️ Task #{setting['id']}: From {setting['source_channel_id']} to {setting['target_channel_id']}", callback_data=f"select_test_setting_{setting['id']}")])
    keyboard.append([InlineKeyboardButton("⬅️ ត្រលប់ក្រោយ", callback_data="back_to_main")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_html(
        """<b>🧪 សាកល្បង Forward សារ</b>

សូមជ្រើសរើស Task ដែលអ្នកចង់សាកល្បង (Bot នឹងប្រើ Caption និងការកំណត់លុប Tags របស់ Task នោះ)៖""",
        reply_markup=reply_markup
    )
    return TEST_FORWARD_PROMPT_ID

async def test_forward(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Allows user to test the forwarding logic with a specific message ID."""
    query = update.callback_query
    await query.answer()
    setting_id = int(query.data.replace("select_test_setting_", ""))
    
    setting = get_setting_by_id(setting_id)
    if not setting:
        await query.edit_message_text("⚠️ រកមិនឃើញ Task នេះទេ។")
        return ConversationHandler.END

    context.user_data['test_forward_setting'] = dict(setting) # Store as dict

    await query.edit_message_text(
        f"""<b>🧪 សាកល្បង Forward សារ (Task #{setting_id})</b>
From <code>{setting['source_channel_id']}</code> to <code>{setting['target_channel_id']}</code>

<b>➡️ សូមផ្ញើ ID របស់សារដែលអ្នកចង់ Forward ពី Channel ប្រភព។</b>""",
        parse_mode=ParseMode.HTML
    )
    return BROADCAST_PROMPT_MESSAGE_ID 

async def test_forward_execute(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Executes the test forward based on message ID using _send_message_content."""
    try:
        message_id_to_forward = int(update.message.text.strip())
        setting = context.user_data.get('test_forward_setting')

        if not setting:
            await update.message.reply_html("⚠️ មានបញ្ហា! ព័ត៌មាន Task មិនពេញលេញទេ។ សូមសាកល្បងម្តងទៀត។")
            return ConversationHandler.END
        
        # We need to temporarily update the 'current_message_id' in the setting dict for the helper function
        setting['current_message_id'] = message_id_to_forward
        
        await update.message.reply_html("⏳ កំពុងព្យាយាម Forward... សូមរង់ចាំ។")

        success = await _send_message_content_by_id(context, setting)

        if success == True:
            await update.message.reply_html(
                f"✅ បាន Forward សារ ID <code>{message_id_to_forward}</code> ទៅកាន់ <code>{setting['target_channel_id']}</code> ដោយជោគជ័យ!"
            )
        elif success == 'not_found':
            await update.message.reply_html(
                f"""<b>⚠️ រកមិនឃើញសារ/មិនអាច Forward បានទេ។</b>
មិនអាចរកឃើញសារ ID <code>{message_id_to_forward}</code> នៅក្នុង Channel <code>{setting['source_channel_id']}</code> ទេ។"""
            )
        else:
            await update.message.reply_html(
                f"<b>⚠️ មានបញ្ហាក្នុងការ Forward សារសាកល្បង។</b> សូមប្រាកដថា ID សារត្រឹមត្រូវ "
                f"និង Bot គឺជា Admin នៅក្នុង Channel ទាំងពីរ។"
            )

        context.user_data.pop('test_forward_setting', None)
        return ConversationHandler.END

    except ValueError:
        await update.message.reply_html("<b>⚠️ ID សារមិនត្រឹមត្រូវទេ។</b> សូមផ្ញើ ID សារដែលជាលេខ។")
        return BROADCAST_PROMPT_MESSAGE_ID


def get_test_forward_conv_handler() -> ConversationHandler:
    """Returns the ConversationHandler for testing forwards."""
    return ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^សាកល្បង Forward 🧪$"), test_forward_prompt_id)],
        states={
            TEST_FORWARD_PROMPT_ID: [
                CallbackQueryHandler(test_forward, pattern=re.compile("^select_test_setting_")),
                CallbackQueryHandler(back_to_main_menu, pattern="^back_to_main$"),
            ],
            BROADCAST_PROMPT_MESSAGE_ID: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, test_forward_execute),
            ],
        },
        fallbacks=[CommandHandler("start", start), MessageHandler(filters.Regex("^សាកល្បង Forward 🧪$"), test_forward_prompt_id)],
        per_message=False
    )
