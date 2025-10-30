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

from ..core.database import (
    get_user_forward_settings,
    get_setting_by_id,
    add_forward_setting,
    update_setting_active,
    update_setting_caption,
    update_setting_remove_tags,
    delete_setting_by_id
)
from .helpers import validate_channel_id
from .start import start, back_to_main_menu
from ..jobs import stop_job_for_task, schedule_id_range_task

logger = logging.getLogger(__name__)

# Conversation states
(SELECT_FORWARD_OPTION, SELECT_TASK_TYPE, ADD_SOURCE_CHANNEL, ADD_TARGET_CHANNEL, 
 SET_CUSTOM_CAPTION, CONFIRM_REMOVE_CAPTION, PROMPT_START_ID, PROMPT_END_ID, 
 PROMPT_EVERY_N, PROMPT_INTERVAL, MANAGE_TASKS_MENU,
 EDIT_CAPTION_PROMPT, TOGGLE_REMOVE_CAPTION_MENU) = range(13)

# --- Settings Conversation ---

async def settings_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Shows the settings menu."""
    keyboard = [
        [InlineKeyboardButton("➕ បន្ថែម Task ថ្មី", callback_data="add_task")],
        [InlineKeyboardButton("🔧 គ្រប់គ្រង Tasks (Pause/Resume/Delete)", callback_data="manage_tasks_menu")],
        [InlineKeyboardButton("📝 កែ Caption", callback_data="edit_caption_menu")],
        [InlineKeyboardButton("🗑️ បើក/បិទ លុប Caption ដើម", callback_data="toggle_remove_caption_menu")],
        [InlineKeyboardButton("👁️ មើល Tasks បច្ចុប្បន្ន", callback_data="view_current_settings")],
        [InlineKeyboardButton("⬅️ ត្រលប់ក្រោយ", callback_data="back_to_main")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    message_text = "<b>⚙️ ការកំណត់ Bot</b>\n\nសូមជ្រើសរើសការកំណត់ដែលអ្នកចង់ធ្វើ៖"

    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.message.edit_text(text=message_text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
    else:
        await update.message.reply_html(text=message_text, reply_markup=reply_markup)
    return SELECT_FORWARD_OPTION

async def prompt_task_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Asks user to select the task type."""
    query = update.callback_query
    await query.answer()
    keyboard = [
        [InlineKeyboardButton("Auto Forward សារថ្មីៗ", callback_data="task_new_messages")],
        [InlineKeyboardButton("Forward តាម ID Range", callback_data="task_id_range")],
        [InlineKeyboardButton("⬅️ ត្រលប់ក្រោយ", callback_data="back_to_settings")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        """<b>➕ បន្ថែម Task ថ្មី</b>

សូមជ្រើសរើសប្រភេទ Task ដែលអ្នកចង់បង្កើត៖

1.  <b>Auto Forward សារថ្មីៗ:</b> Bot នឹងពិនិត្យ និង Forward សារថ្មីៗដោយស្វ័យប្រវត្តិ (តាមរយៈ Webhook)។
2.  <b>Forward តាម ID Range:</b> Bot នឹង Forward សារចាស់ៗ ដោយផ្អែកលើ ID ចាប់ផ្តើម និង ID បញ្ចប់ ដែលអ្នកកំណត់ (តាមរយៈ Job)។""",
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML
    )
    return SELECT_TASK_TYPE

async def receive_task_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receives task type and prompts for source channel."""
    query = update.callback_query
    await query.answer()
    context.user_data['task_type'] = query.data.replace("task_", "") # 'new_messages' or 'id_range'
    
    await query.edit_message_text(
        """<b>➕ បន្ថែម Channel ប្រភព</b>

សូមផ្ញើ ID របស់ Channel ប្រភព (Source Channel ID)។
<b>សំខាន់:</b> Bot ត្រូវតែជា Admin នៅក្នុង Channel នោះ។
ឧទាហរណ៍: <code>-1001234567890</code>""",
        parse_mode=ParseMode.HTML
    )
    return ADD_SOURCE_CHANNEL

async def receive_source_channel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receives source channel ID."""
    source_id, next_state = await validate_channel_id(update, context, ADD_TARGET_CHANNEL)
    if not source_id:
        return ADD_SOURCE_CHANNEL
        
    context.user_data['source_channel_id'] = source_id
    await update.message.reply_html(
        f"""✅ បានទទួល Source Channel ID: <code>{source_id}</code>។

<b>➡️ ឥឡូវសូមផ្ញើ ID របស់ Channel គោលដៅ (Target Channel ID)។</b>
<b>សំខាន់:</b> Bot ត្រូវតែជា Admin នៅក្នុង Channel នោះ។"""
    )
    return ADD_TARGET_CHANNEL

async def receive_target_channel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receives target channel ID."""
    target_id, next_state = await validate_channel_id(update, context, SET_CUSTOM_CAPTION)
    if not target_id:
        return ADD_TARGET_CHANNEL
    
    context.user_data['target_channel_id'] = target_id
    await update.message.reply_html(
        f"""✅ បានទទួល Target Channel ID: <code>{target_id}</code>។

<b>📝 ឥឡូវនេះ សូមផ្ញើ Caption ផ្ទាល់ខ្លួន។</b>
អ្នកអាចប្រើ HTML tags (<b>Bold</b>, <i>Italic</i>, <a href='URL'>Link</a>)។
ប្រសិនបើមិនចង់បាន Caption ផ្ទាល់ខ្លួនទេ សូមវាយ <code>none</code> ។"""
    )
    return SET_CUSTOM_CAPTION

async def set_custom_caption(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Sets custom caption."""
    custom_caption = update.message.text
    context.user_data['custom_caption'] = "" if custom_caption.lower() == 'none' else custom_caption

    keyboard = [
        [InlineKeyboardButton("✅ បាទ/ចាស (ណែនាំ)", callback_data="remove_caption_yes")],
        [InlineKeyboardButton("❌ ទេ (រក្សាទុក caption ដើម)", callback_data="remove_caption_no")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_html(
        """<b>🗑️ តើអ្នកចង់លុប Caption ដើមចេញពីសារដែរឬទេ?</b>
('បាទ/ចាស' នឹងធ្វើឱ្យសារមើលទៅដូចជា 'Copy'។ 'ទេ' នឹងបន្ថែម Caption របស់អ្នកពីក្រោម Caption ដើម)""",
        reply_markup=reply_markup
    )
    return CONFIRM_REMOVE_CAPTION

async def confirm_remove_caption(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Confirms remove caption and routes to next step based on task type."""
    query = update.callback_query
    await query.answer()
    context.user_data['remove_tags_caption'] = True if query.data == "remove_caption_yes" else False
    
    task_type = context.user_data['task_type']
    
    if task_type == 'id_range':
        await query.edit_message_text(
            """<b>🗓️ កំណត់ ID Range</b>

<b>➡️ សូមផ្ញើ ID របស់សារដែលត្រូវចាប់ផ្តើម (Start Message ID)។</b>
(ឧទាហរណ៍: <code>1500</code>)""",
            parse_mode=ParseMode.HTML
        )
        return PROMPT_START_ID
    else: # 'new_messages'
        # For 'new_messages', we just save it. No interval is needed as it's webhook-driven.
        context.user_data['interval_seconds'] = 0 # Not applicable
        return await save_new_task(update, context)


async def receive_start_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        start_id = int(update.message.text.strip())
        if start_id <= 0:
            await update.message.reply_html("<b>⚠️ ID ត្រូវតែជាលេខវិជ្ជមាន។</b>")
            return PROMPT_START_ID
        
        context.user_data['start_message_id'] = start_id
        await update.message.reply_html(
            f"""✅ ID ចាប់ផ្តើម: <code>{start_id}</code>

<b>➡️ ឥឡូវនេះ សូមផ្ញើ ID របស់សារដែលត្រូវបញ្ចប់ (End Message ID)។</b>
(ឧទាហរណ៍: <code>2000</code>)"""
        )
        return PROMPT_END_ID

    except ValueError:
        await update.message.reply_html("<b>⚠️ ID មិនត្រឹមត្រូវទេ។</b> សូមផ្ញើជាលេខ។")
        return PROMPT_START_ID

async def receive_end_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        end_id = int(update.message.text.strip())
        start_id = context.user_data['start_message_id']
        if end_id <= start_id:
            await update.message.reply_html(f"<b>⚠️ End ID ត្រូវតែធំជាង Start ID (<code>{start_id}</code>)។</b>")
            return PROMPT_END_ID
        
        context.user_data['end_message_id'] = end_id
        await update.message.reply_html(
            f"""✅ ID បញ្ចប់: <code>{end_id}</code>

<b>➡️ ដំណើរការរាល់ (Every 'N' Posts)?</b>
សូមផ្ញើលេខ <code>1</code> ប្រសិនបើចង់ Forward គ្រប់ Post ក្នុង Range នេះ។
សូមផ្ញើលេខ <code>2</code> ប្រសិនបើចង់ Forward ឆ្លង 1 (Post ទី 1, 3, 5...)"""
        )
        return PROMPT_EVERY_N

    except ValueError:
        await update.message.reply_html("<b>⚠️ ID មិនត្រឹមត្រូវទេ។</b> សូមផ្ញើជាលេខ។")
        return PROMPT_END_ID

async def receive_every_n(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        every_n = int(update.message.text.strip())
        if every_n <= 0:
            await update.message.reply_html("<b>⚠️ លេខត្រូវតែធំជាង 0។</b>")
            return PROMPT_EVERY_N
        
        context.user_data['forward_every_n_posts'] = every_n
        await update.message.reply_html(
            f"""✅ ដំណើរការរាល់: <code>{every_n}</code> Post

<b>⏱️ កំណត់ពេលវេលា</b>

<b>➡️ សូមផ្ញើ Interval (គិតជាវិនាទី) រវាង Post នីមួយៗ។</b>
ឧទាហរណ៍: <code>5</code> (សម្រាប់ 5 វិនាទី), <code>60</code> (សម្រាប់ 1 នាទី)។
<b>ចំណាំ:</b> កំណត់ពេល <code>1</code> វិនាទី គឺលឿនណាស់ អាចប្រឈមនឹងការប្លុកពី Telegram (Flood Wait)។"""
        )
        return PROMPT_INTERVAL

    except ValueError:
        await update.message.reply_html("<b>⚠️ មិនត្រឹមត្រូវទេ។</b> សូមផ្ញើជាលេខ។")
        return PROMPT_EVERY_N

async def receive_interval_and_save(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receives interval and saves the new ID_RANGE task, then schedules it."""
    try:
        interval_seconds = int(update.message.text.strip())
        if interval_seconds <= 0:
            await update.message.reply_html("<b>⚠️ Interval ត្រូវតែធំជាង 0។</b>")
            return PROMPT_INTERVAL
        
        context.user_data['interval_seconds'] = interval_seconds
        
        # This function is now only for ID_RANGE, so we call save_new_task
        return await save_new_task(update, context)

    except ValueError:
        await update.message.reply_html("<b>⚠️ មិនត្រឹមត្រូវទេ។</b> សូមផ្ញើជាលេខ។")
        return PROMPT_INTERVAL

async def save_new_task(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Saves the new task (both types) to the DB and schedules if needed."""
    try:
        # Determine the user ID from callback or message
        user_id = update.effective_user.id
        
        # Gather all data
        data = {
            'user_id': user_id,
            'source_channel_id': context.user_data['source_channel_id'],
            'target_channel_id': context.user_data['target_channel_id'],
            'custom_caption': context.user_data['custom_caption'],
            'remove_tags_caption': context.user_data['remove_tags_caption'],
            'task_type': context.user_data['task_type'],
            'interval_seconds': context.user_data.get('interval_seconds', 0),
            'start_message_id': context.user_data.get('start_message_id', 0),
            'end_message_id': context.user_data.get('end_message_id', 0),
            'forward_every_n_posts': context.user_data.get('forward_every_n_posts', 1)
        }
        
        # Save to DB
        setting_id = add_forward_setting(data)
        
        reply_message = f"<b>✅ Task #{setting_id} ត្រូវបានបង្កើត!</b>"
        
        # Schedule the job ONLY if it's an 'id_range' task
        if data['task_type'] == 'id_range':
            schedule_id_range_task(context.job_queue, setting_id, data['interval_seconds'])
            reply_message += "\nJob សម្រាប់ ID Range បានចាប់ផ្តើមដំណើរការ។"
        else:
            reply_message += "\nBot នឹងចាប់ផ្តើមស្តាប់សារថ្មីៗពី Channel នេះ។"

        # Determine how to reply
        if update.callback_query:
            await update.callback_query.edit_message_text(reply_message, parse_mode=ParseMode.HTML)
        else:
            await update.message.reply_html(reply_message)
        
        # Clear user_data
        context.user_data.clear()
        
        # Show the settings menu again
        # We need a new update object for settings_menu if called from a message
        if update.callback_query:
            await settings_menu(update, context)
        
        return ConversationHandler.END

    except Exception as e:
        logger.error(f"Error saving setting: {e}", exc_info=True)
        error_message = f"<b>⚠️ មានបញ្ហាក្នុងការរក្សាទុក:</b> {e}"
        if update.callback_query:
            await update.callback_query.edit_message_text(error_message, parse_mode=ParseMode.HTML)
        else:
            await update.message.reply_html(error_message)
        return ConversationHandler.END


# --- Manage Other Settings (Edit Caption, Toggle Remove, View) ---

async def view_current_settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Displays current forward settings for the user."""
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    settings = get_user_forward_settings(user_id)

    status_message = "<b>👁️ Tasks បច្ចុប្បន្នរបស់អ្នក:</b>\n"
    if not settings:
        status_message += "អ្នកមិនទាន់បានកំណត់ Task ណាមួយនៅឡើយទេ។"
    else:
        for i, setting in enumerate(settings):
            task_type = setting.get('task_type', 'new_messages') 
            
            status_message += f"\n<b>✨ Task #{setting['id']}</b> ({'សកម្ម ✅' if setting['is_active'] else 'ផ្អាក ⏸️'})\n"
            status_message += f"  <b>- ប្រភេទ:</b> {'សារថ្មីៗ' if task_type == 'new_messages' else 'តាម ID Range'}\n"
            status_message += f"  <b>- Source:</b> <code>{setting['source_channel_id']}</code>\n"
            status_message += f"  <b>- Target:</b> <code>{setting['target_channel_id']}</code>\n"
            status_message += f"  <b>- Caption:</b> {setting['custom_caption'] or 'គ្មាន'}\n"
            status_message += f"  <b>- លុប Caption ដើម:</b> {'បាទ/ចាស' if setting['remove_tags_caption'] else 'ទេ'}\n"
            
            if task_type == 'id_range':
                status_message += f"  <b>- Interval:</b> {setting.get('interval_seconds', 'N/A')} វិនាទី\n"
                status_message += f"  <b>- ID Range:</b> <code>{setting.get('start_message_id', 0)}</code> ដល់ <code>{setting.get('end_message_id', 0)}</code>\n"
                status_message += f"  <b>- ID បច្ចុប្បន្ន:</b> <code>{setting.get('current_message_id', 0)}</code>\n"
                status_message += f"  <b>- ដំណើរការរាល់:</b> {setting.get('forward_every_n_posts', 1)} post\n"
            else:
                status_message += f"  <b>- សារចុងក្រោយ:</b> <code>{setting.get('last_processed_message_id', 0)}</code>\n"

    keyboard = [[InlineKeyboardButton("⬅️ ត្រលប់ក្រោយ", callback_data="back_to_settings")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(status_message, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
    return SELECT_FORWARD_OPTION

async def set_custom_caption_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Prompts user to select a task to edit its caption."""
    query = update.callback_query
    await query.answer()
    settings = get_user_forward_settings(update.effective_user.id)
    if not settings:
        await query.edit_message_text("អ្នកមិនទាន់មាន Task ណាមួយទេ។", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ ត្រលប់ក្រោយ", callback_data="back_to_settings")]]))
        return SELECT_FORWARD_OPTION

    keyboard = []
    for setting in settings:
        caption_preview = setting['custom_caption'] or "គ្មាន"
        if len(caption_preview) > 20:
             caption_preview = caption_preview[:20] + "..."
        keyboard.append([InlineKeyboardButton(f"📝 Task #{setting['id']} (Caption: {caption_preview})", callback_data=f"edit_caption_{setting['id']}")])
    keyboard.append([InlineKeyboardButton("⬅️ ត្រលប់ក្រោយ", callback_data="back_to_settings")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text("<b>📝 កំណត់ Caption ផ្ទាល់ខ្លួន</b>\n\nសូមជ្រើសរើស Task ដែលអ្នកចង់កែ Caption៖", reply_markup=reply_markup, parse_mode=ParseMode.HTML)
    return EDIT_CAPTION_PROMPT

async def prompt_edit_custom_caption(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Prompts for new custom caption."""
    query = update.callback_query
    await query.answer()
    setting_id = int(query.data.replace("edit_caption_", ""))
    context.user_data['setting_to_edit_caption'] = setting_id
    
    setting = get_setting_by_id(setting_id)
    current_caption = setting['custom_caption'] or "គ្មាន"

    await query.edit_message_text(
        f"""<b>📝 កំណត់ Caption ផ្ទាល់ខ្លួន (Task #{setting_id})</b>
Caption បច្ចុប្បន្ន៖ <code>{current_caption}</code>

<b>➡️ សូមផ្ញើ Caption ថ្មី។</b> (វាយ <code>none</code> ដើម្បីលុប Caption)""",
        parse_mode=ParseMode.HTML
    )
    return SET_CUSTOM_CAPTION # Re-use this state

async def save_edited_caption(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Saves the edited custom caption."""
    setting_id = context.user_data.get('setting_to_edit_caption')
    if not setting_id:
        return ConversationHandler.END

    new_caption = update.message.text
    if new_caption.lower() == 'none':
        new_caption = ""
    
    update_setting_caption(setting_id, new_caption)
    
    await update.message.reply_html(f"✅ Caption សម្រាប់ Task #{setting_id} ត្រូវបានអាប់ដេត។")
    
    context.user_data.pop('setting_to_edit_caption', None)
    # We can't call settings_menu here directly as it expects a message or query
    return ConversationHandler.END

async def toggle_remove_caption_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Shows menu to toggle remove_tags_caption for tasks."""
    query = update.callback_query
    await query.answer()
    settings = get_user_forward_settings(update.effective_user.id)
    if not settings:
        await query.edit_message_text("អ្នកមិនទាន់មាន Task ណាមួយទេ។", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ ត្រលប់ក្រោយ", callback_data="back_to_settings")]]))
        return SELECT_FORWARD_OPTION

    keyboard = []
    for setting in settings:
        status_text = "បើក (កំពុងលុប)" if setting['remove_tags_caption'] else "បិទ (កំពុងរក្សាទុក)"
        keyboard.append([InlineKeyboardButton(f"⚙️ Task #{setting['id']} ({status_text})", callback_data=f"toggle_remove_{setting['id']}")])
    keyboard.append([InlineKeyboardButton("⬅️ ត្រលប់ក្រោយ", callback_data="back_to_settings")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text("<b>🗑️ បើក/បិទ លុប Caption ដើម</b>\n\nសូមជ្រើសរើស Task ដើម្បីប្តូរការកំណត់៖", reply_markup=reply_markup, parse_mode=ParseMode.HTML)
    return TOGGLE_REMOVE_CAPTION_MENU

async def execute_toggle_remove_caption(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Executes the toggle for remove_tags_caption."""
    query = update.callback_query
    await query.answer()
    setting_id = int(query.data.replace("toggle_remove_", ""))
    
    setting = get_setting_by_id(setting_id)
    if setting:
        new_state = not setting['remove_tags_caption']
        update_setting_remove_tags(setting_id, new_state)
        await query.answer(
            f"✅ ការកំណត់សម្រាប់ Task #{setting_id} ត្រូវបានប្តូរទៅ {'បើក' if new_state else 'បិទ'}។",
            show_alert=True
        )
    else:
        await query.answer("⚠️ រកមិនឃើញ Task នេះទេ។", show_alert=True)
    
    # Refresh the menu
    await toggle_remove_caption_menu(update, context)
    return TOGGLE_REMOVE_CAPTION_MENU


# --- Manage Tasks (Pause, Resume, Delete) ---

async def manage_tasks_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Displays tasks for management (Pause/Resume/Delete)."""
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    settings = get_user_forward_settings(user_id)

    if not settings:
        await query.edit_message_text("អ្នកមិនទាន់មាន Task ណាមួយទេ។", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ ត្រលប់ក្រោយ", callback_data="back_to_settings")]]))
        return SELECT_FORWARD_OPTION

    keyboard = []
    for setting in settings:
        status_icon = "⏸️" if setting['is_active'] else "▶️"
        status_text = "Pause" if setting['is_active'] else "Resume"
        keyboard.append([
            InlineKeyboardButton(f"Task #{setting['id']} (Source: {setting['source_channel_id']})", callback_data=f"task_info_{setting['id']}"),
            InlineKeyboardButton(f"{status_icon} {status_text}", callback_data=f"task_toggle_{setting['id']}"),
            InlineKeyboardButton("❌ Delete", callback_data=f"task_delete_{setting['id']}")
        ])
    keyboard.append([InlineKeyboardButton("⬅️ ត្រលប់ក្រោយ", callback_data="back_to_settings")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "<b>🔧 គ្រប់គ្រង Tasks</b>\n\nសូមជ្រើសរើស Task ដើម្បី Pause, Resume, ឬ Delete៖",
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML
    )
    return MANAGE_TASKS_MENU

async def manage_task_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles Pause/Resume/Delete actions."""
    query = update.callback_query
    await query.answer()
    
    parts = query.data.split("_")
    if len(parts) < 3:
        logger.error(f"Invalid callback data in manage_task_action: {query.data}")
        return MANAGE_TASKS_MENU 

    action = f"{parts[0]}_{parts[1]}" # e.g., "task_toggle"
    setting_id_str = parts[2]
    
    try:
        setting_id = int(setting_id_str)
    except ValueError:
        logger.error(f"Invalid setting ID in manage_task_action: {setting_id_str}")
        return MANAGE_TASKS_MENU

    
    if action == "task_toggle":
        setting = get_setting_by_id(setting_id)
        if not setting:
            await query.answer("⚠️ រកមិនឃើញ Task នេះទេ។", show_alert=True)
            return MANAGE_TASKS_MENU

        if setting['is_active']:
            # Pause the task
            update_setting_active(setting_id, False)
            if setting['task_type'] == 'id_range':
                stop_job_for_task(context, setting_id)
            await query.answer(f"✅ Task #{setting_id} ត្រូវបានផ្អាក (Paused)។", show_alert=True)
        else:
            # Resume the task
            update_setting_active(setting_id, True)
            if setting['task_type'] == 'id_range':
                schedule_id_range_task(context.job_queue, setting_id, setting['interval_seconds'])
            await query.answer(f"✅ Task #{setting_id} ត្រូវបានបន្ត (Resumed)។", show_alert=True)
            
    elif action == "task_delete":
        # Delete the task
        setting = get_setting_by_id(setting_id)
        if setting and setting['task_type'] == 'id_range':
            stop_job_for_task(context, setting_id)
        
        delete_setting_by_id(setting_id)
        await query.answer(f"✅ Task #{setting_id} ត្រូវបានលុប។", show_alert=True)
        
    elif action == "task_info":
        await query.answer("ℹ️ នេះគឺជាព័ត៌មាន Task។", show_alert=False)
        return MANAGE_TASKS_MENU # Stay on this menu

    # Refresh the menu
    await manage_tasks_menu(update, context)
    return MANAGE_TASKS_MENU


def get_settings_conv_handler() -> ConversationHandler:
    """Returns the ConversationHandler for bot settings."""
    return ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^ការកំណត់ Bot ⚙️$"), settings_menu),
            CallbackQueryHandler(settings_menu, pattern="^back_to_settings$")
        ],
        states={
            SELECT_FORWARD_OPTION: [
                CallbackQueryHandler(prompt_task_type, pattern="^add_task$"),
                CallbackQueryHandler(manage_tasks_menu, pattern="^manage_tasks_menu$"),
                CallbackQueryHandler(set_custom_caption_menu, pattern="^edit_caption_menu$"),
                CallbackQueryHandler(toggle_remove_caption_menu, pattern="^toggle_remove_caption_menu$"),
                CallbackQueryHandler(view_current_settings, pattern="^view_current_settings$"),
                CallbackQueryHandler(back_to_main_menu, pattern="^back_to_main$"),
            ],
            MANAGE_TASKS_MENU: [
                CallbackQueryHandler(manage_task_action, pattern=re.compile("^(task_toggle_|task_delete_|task_info_)")),
                CallbackQueryHandler(settings_menu, pattern="^back_to_settings$"),
            ],
            SELECT_TASK_TYPE: [
                CallbackQueryHandler(receive_task_type, pattern=re.compile("^(task_new_messages|task_id_range)$")),
                CallbackQueryHandler(settings_menu, pattern="^back_to_settings$"),
            ],
            ADD_SOURCE_CHANNEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_source_channel)],
            ADD_TARGET_CHANNEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_target_channel)],
            SET_CUSTOM_CAPTION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, set_custom_caption),
                MessageHandler(filters.TEXT & ~filters.COMMAND, save_edited_caption, block=False) # Handle save edit
            ],
            CONFIRM_REMOVE_CAPTION: [CallbackQueryHandler(confirm_remove_caption, pattern="^remove_caption_(yes|no)$")],
            PROMPT_START_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_start_id)],
            PROMPT_END_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_end_id)],
            PROMPT_EVERY_N: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_every_n)],
            PROMPT_INTERVAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_interval_and_save)],
            EDIT_CAPTION_PROMPT: [
                CallbackQueryHandler(prompt_edit_custom_caption, pattern=re.compile("^edit_caption_")),
                CallbackQueryHandler(settings_menu, pattern="^back_to_settings$"),
            ],
            TOGGLE_REMOVE_CAPTION_MENU: [
                CallbackQueryHandler(execute_toggle_remove_caption, pattern=re.compile("^toggle_remove_")),
                CallbackQueryHandler(settings_menu, pattern="^back_to_settings$"),
            ],
        },
        fallbacks=[CommandHandler("start", start), MessageHandler(filters.Regex("^ការកំណត់ Bot ⚙️$"), settings_menu)],
        per_message=False
    )
