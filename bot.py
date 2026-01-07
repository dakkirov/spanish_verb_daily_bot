import os
import asyncio
import logging
import random
from datetime import datetime, time
from zoneinfo import ZoneInfo

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import (
    Application, 
    CommandHandler, 
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
    JobQueue
)

import database as db
from verbs import VERBS, get_verb_by_index, get_random_verb, get_verb_count
from translations import get_text, TRANSLATIONS

# Bot token - use environment variable
BOT_TOKEN = os.environ.get("BOT_TOKEN")

# Logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Supported languages for translation
LANGUAGES = {
    'english': '🇬🇧 English',
    'portuguese': '🇧🇷 Português', 
    'french': '🇫🇷 Français',
    'italian': '🇮🇹 Italiano',
    'german': '🇩🇪 Deutsch',
    'russian': '🇷🇺 Русский'
}

# Common timezones
TIMEZONES = {
    'America/Argentina/Buenos_Aires': '🇦🇷 Argentina (Buenos Aires)',
    'America/New_York': '🇺🇸 US Eastern',
    'America/Los_Angeles': '🇺🇸 US Pacific',
    'America/Sao_Paulo': '🇧🇷 Brazil (São Paulo)',
    'Europe/London': '🇬🇧 London',
    'Europe/Madrid': '🇪🇸 Spain',
    'Europe/Paris': '🇫🇷 Paris',
    'Europe/Berlin': '🇩🇪 Berlin',
    'Asia/Tokyo': '🇯🇵 Tokyo',
    'Europe/Moscow': '🇷🇺 Moscow',
    'UTC': '🌍 UTC'
}

# Time options
TIME_OPTIONS = ['07:00', '08:00', '09:00', '10:00', '12:00', '18:00', '20:00', '21:00']


def get_user_lang(user_id: int) -> str:
    """Get user's language preference, default to English."""
    user = db.get_user(user_id)
    if user and user.get('language'):
        return user['language']
    return 'english'


def format_verb_message(verb: dict, language: str) -> str:
    """Format a verb for display."""
    translation = verb['translations'].get(language, verb['translations']['english'])
    
    presente = verb['presente']
    pasado = verb['pasado']
    futuro = verb['futuro']
    
    message = f"""🇦🇷 <b>Verbo del Día</b>

<b>{verb['infinitive'].upper()}</b>
({translation})

📖 <i>{verb['definition']}</i>

🕐 <b>Presente:</b>
yo {presente['yo']}, vos {presente['vos']}, él/ella {presente['él/ella']}
nosotros {presente['nosotros']}, ustedes {presente['ustedes']}, ellos {presente['ellos/ellas']}

⏪ <b>Pasado:</b>
yo {pasado['yo']}, vos {pasado['vos']}, él/ella {pasado['él/ella']}
nosotros {pasado['nosotros']}, ustedes {pasado['ustedes']}, ellos {pasado['ellos/ellas']}

⏩ <b>Futuro:</b>
yo {futuro['yo']}, vos {futuro['vos']}, él/ella {futuro['él/ella']}
nosotros {futuro['nosotros']}, ustedes {futuro['ustedes']}, ellos {futuro['ellos/ellas']}"""
    
    return message


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command - begin onboarding."""
    user = update.effective_user
    db_user = db.get_user(user.id)
    
    if db_user and db_user['onboarding_complete']:
        # User already set up - use their language
        lang = db_user['language']
        await update.message.reply_text(
            get_text("welcome_back", lang),
            parse_mode='HTML'
        )
        return
    
    # Create or reset user
    db.create_user(user.id, user.username)
    db.update_user(user.id, onboarding_step='language', onboarding_complete=0)
    
    # Start onboarding - language selection (shown in English since no language chosen yet)
    await update.message.reply_text(
        get_text("welcome_intro", "english"),
        parse_mode='HTML',
        reply_markup=get_language_keyboard()
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command."""
    lang = get_user_lang(update.effective_user.id)
    await update.message.reply_text(
        get_text("help_message", lang), 
        parse_mode='HTML'
    )


async def handle_unknown_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle any non-command text message."""
    lang = get_user_lang(update.effective_user.id)
    await update.message.reply_text(get_text("unknown_message", lang))


async def handle_file_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle file uploads (photos, documents, etc.)."""
    lang = get_user_lang(update.effective_user.id)
    await update.message.reply_text(get_text("file_upload", lang))


def get_language_keyboard():
    """Get language selection keyboard."""
    keyboard = []
    for lang_code, lang_name in LANGUAGES.items():
        keyboard.append([InlineKeyboardButton(lang_name, callback_data=f"lang_{lang_code}")])
    return InlineKeyboardMarkup(keyboard)


def get_timezone_keyboard():
    """Get timezone selection keyboard."""
    keyboard = []
    for tz_code, tz_name in TIMEZONES.items():
        keyboard.append([InlineKeyboardButton(tz_name, callback_data=f"tz_{tz_code}")])
    return InlineKeyboardMarkup(keyboard)


def get_time_keyboard():
    """Get time selection keyboard."""
    keyboard = []
    row = []
    for i, t in enumerate(TIME_OPTIONS):
        row.append(InlineKeyboardButton(t, callback_data=f"time_{t}"))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    return InlineKeyboardMarkup(keyboard)


async def handle_onboarding_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle onboarding button presses."""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    data = query.data
    user = db.get_user(user_id)
    
    if not user:
        return
    
    if data.startswith('lang_'):
        # Language selected
        language = data.replace('lang_', '')
        db.update_user(user_id, language=language, onboarding_step='timezone')
        
        # Now use the selected language for all messages
        await query.edit_message_text(
            get_text("language_selected", language, lang=LANGUAGES[language]),
            parse_mode='HTML',
            reply_markup=get_timezone_keyboard()
        )
    
    elif data.startswith('tz_'):
        # Timezone selected
        timezone = data.replace('tz_', '')
        db.update_user(user_id, timezone=timezone, onboarding_step='time')
        
        lang = user['language']
        await query.edit_message_text(
            get_text("select_time", lang),
            parse_mode='HTML',
            reply_markup=get_time_keyboard()
        )
    
    elif data.startswith('time_'):
        # Time selected - onboarding complete!
        daily_time = data.replace('time_', '')
        db.update_user(user_id, daily_time=daily_time, onboarding_complete=1, onboarding_step='done')
        
        user = db.get_user(user_id)
        lang = user['language']
        
        # Schedule the daily job for this user
        schedule_user_daily_verb(context.application, user)
        
        await query.edit_message_text(
            get_text("setup_complete", lang, 
                     lang=LANGUAGES[user['language']], 
                     time=daily_time, 
                     tz=user['timezone']),
            parse_mode='HTML'
        )
        
        # Send first verb
        await send_verb_to_user(context.application.bot, user_id)


async def verb_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /verb command - send a random verb."""
    user_id = update.effective_user.id
    user = db.get_user(user_id)
    lang = get_user_lang(user_id)
    
    if not user or not user['onboarding_complete']:
        await update.message.reply_text(get_text("setup_required", lang))
        return
    
    await send_verb_to_user(context.bot, user_id)


async def send_verb_to_user(bot, user_id: int):
    """Send a verb to a specific user."""
    user = db.get_user(user_id)
    if not user:
        return
    
    # Get verbs not yet sent to this user
    sent_indices = db.get_sent_verb_indices(user_id)
    available_indices = [i for i in range(get_verb_count()) if i not in sent_indices]
    
    # If all verbs sent, reset and start over
    if not available_indices:
        available_indices = list(range(get_verb_count()))
    
    # Pick random verb
    verb_index = random.choice(available_indices)
    verb = get_verb_by_index(verb_index)
    
    # Record and send
    db.record_sent_verb(user_id, verb_index)
    
    message = format_verb_message(verb, user['language'])
    await bot.send_message(user_id, message, parse_mode='HTML')


async def quiz_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /quiz command."""
    user_id = update.effective_user.id
    user = db.get_user(user_id)
    lang = get_user_lang(user_id)
    
    if not user or not user['onboarding_complete']:
        await update.message.reply_text(get_text("setup_required", lang))
        return
    
    # Get recent verbs
    recent_indices = db.get_recent_verbs(user_id, limit=10)
    
    if len(recent_indices) < 1:
        await update.message.reply_text(get_text("quiz_need_verbs", lang))
        return
    
    # Pick a verb to quiz on
    quiz_verb_index = random.choice(recent_indices)
    quiz_verb = get_verb_by_index(quiz_verb_index)
    
    # Generate quiz question
    question_type = random.choice(['meaning', 'conjugation'])
    
    if question_type == 'meaning':
        # Ask what the verb means
        correct_answer = quiz_verb['translations'][user['language']]
        
        # Get wrong answers from other verbs
        other_indices = [i for i in range(get_verb_count()) if i != quiz_verb_index]
        wrong_indices = random.sample(other_indices, 3)
        wrong_answers = [get_verb_by_index(i)['translations'][user['language']] for i in wrong_indices]
        
        all_answers = [correct_answer] + wrong_answers
        random.shuffle(all_answers)
        
        keyboard = []
        for i, answer in enumerate(all_answers):
            letter = chr(65 + i)  # A, B, C, D
            is_correct = 1 if answer == correct_answer else 0
            keyboard.append([InlineKeyboardButton(
                f"{letter}) {answer}", 
                callback_data=f"quiz_{quiz_verb_index}_meaning_{is_correct}"
            )])
        
        await update.message.reply_text(
            get_text("quiz_title", lang) + 
            get_text("quiz_meaning_question", lang, verb=quiz_verb['infinitive']),
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    else:
        # Ask for conjugation - USE SAME VERB for all options (harder!)
        tense = random.choice(['presente', 'pasado', 'futuro'])
        pronoun = random.choice(['yo', 'vos', 'él/ella'])
        correct_answer = quiz_verb[tense][pronoun]
        
        # Get wrong answers from SAME verb, different tenses/pronouns
        wrong_answers = []
        all_tenses = ['presente', 'pasado', 'futuro']
        all_pronouns = ['yo', 'vos', 'él/ella', 'nosotros', 'ustedes']
        
        # Collect all other conjugations from the same verb
        other_conjugations = []
        for t in all_tenses:
            for p in all_pronouns:
                conj = quiz_verb[t][p]
                if conj != correct_answer and conj not in other_conjugations:
                    other_conjugations.append(conj)
        
        # Pick 3 random wrong answers
        wrong_answers = random.sample(other_conjugations, min(3, len(other_conjugations)))
        
        all_answers = [correct_answer] + wrong_answers
        random.shuffle(all_answers)
        
        # Translate tense name
        tense_key = f"tense_{tense.replace('presente', 'present').replace('pasado', 'past').replace('futuro', 'future')}"
        tense_name = get_text(tense_key, lang)
        
        keyboard = []
        for i, answer in enumerate(all_answers):
            letter = chr(65 + i)
            is_correct = 1 if answer == correct_answer else 0
            keyboard.append([InlineKeyboardButton(
                f"{letter}) {answer}",
                callback_data=f"quiz_{quiz_verb_index}_conjugation_{is_correct}"
            )])
        
        await update.message.reply_text(
            get_text("quiz_title", lang) +
            f"<b>{quiz_verb['infinitive'].upper()}</b>\n\n" +
            get_text("quiz_conjugation_question", lang, tense=tense_name, pronoun=pronoun),
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )


async def handle_quiz_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle quiz answer."""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    lang = get_user_lang(user_id)
    parts = query.data.split('_')
    # quiz_{verb_index}_{type}_{is_correct}
    verb_index = int(parts[1])
    question_type = parts[2]
    is_correct = parts[3] == '1'
    
    # Record result
    db.record_quiz_result(user_id, verb_index, question_type, is_correct)
    
    if is_correct:
        await query.edit_message_text(
            get_text("quiz_correct", lang),
            parse_mode='HTML'
        )
    else:
        verb = get_verb_by_index(verb_index)
        user = db.get_user(user_id)
        translation = verb['translations'][user['language']]
        
        await query.edit_message_text(
            get_text("quiz_incorrect", lang, verb=verb['infinitive'], translation=translation),
            parse_mode='HTML'
        )


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /stats command."""
    user_id = update.effective_user.id
    user = db.get_user(user_id)
    lang = get_user_lang(user_id)
    
    if not user:
        await update.message.reply_text(get_text("use_start", lang))
        return
    
    stats = db.get_quiz_stats(user_id)
    sent_count = len(db.get_sent_verb_indices(user_id))
    
    await update.message.reply_text(
        get_text("stats_title", lang,
                 learned=sent_count,
                 total=get_verb_count(),
                 attempts=stats['total'],
                 correct=stats['correct'],
                 rate=stats['percentage']),
        parse_mode='HTML'
    )


async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /settings command."""
    user_id = update.effective_user.id
    user = db.get_user(user_id)
    lang = get_user_lang(user_id)
    
    if not user:
        await update.message.reply_text(get_text("use_start", lang))
        return
    
    # Get translated status
    status = get_text("status_active", lang) if user['is_active'] else get_text("status_paused", lang)
    
    # Get translated button labels
    pause_btn = get_text("btn_resume", lang) if not user['is_active'] else get_text("btn_pause", lang)
    
    keyboard = [
        [InlineKeyboardButton(get_text("btn_change_language", lang), callback_data="settings_language")],
        [InlineKeyboardButton(get_text("btn_change_time", lang), callback_data="settings_time")],
        [InlineKeyboardButton(get_text("btn_change_timezone", lang), callback_data="settings_timezone")],
        [InlineKeyboardButton(pause_btn, callback_data="settings_pause")],
    ]
    
    await update.message.reply_text(
        get_text("settings_title", lang,
                 lang=LANGUAGES[user['language']],
                 time=user['daily_time'],
                 tz=user['timezone'],
                 status=status),
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def handle_settings_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle settings changes."""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    data = query.data
    lang = get_user_lang(user_id)
    
    if data == "settings_language":
        await query.edit_message_text(
            get_text("select_language", lang),
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(name, callback_data=f"setlang_{code}")]
                for code, name in LANGUAGES.items()
            ])
        )
    
    elif data == "settings_time":
        await query.edit_message_text(
            get_text("select_time", lang),
            reply_markup=get_time_keyboard_settings()
        )
    
    elif data == "settings_timezone":
        await query.edit_message_text(
            get_text("select_timezone", lang),
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(name, callback_data=f"settz_{code}")]
                for code, name in TIMEZONES.items()
            ])
        )
    
    elif data == "settings_pause":
        user = db.get_user(user_id)
        new_status = 0 if user['is_active'] else 1
        db.update_user(user_id, is_active=new_status)
        
        if new_status:
            await query.edit_message_text(get_text("verbs_resumed", lang))
        else:
            await query.edit_message_text(get_text("verbs_paused", lang))
    
    elif data.startswith("setlang_"):
        language = data.replace("setlang_", "")
        db.update_user(user_id, language=language)
        # Use the NEW language for confirmation message
        await query.edit_message_text(
            get_text("language_changed", language, lang=LANGUAGES[language])
        )
    
    elif data.startswith("settime_"):
        new_time = data.replace("settime_", "")
        db.update_user(user_id, daily_time=new_time)
        
        # Reschedule
        user = db.get_user(user_id)
        schedule_user_daily_verb(context.application, user)
        
        await query.edit_message_text(
            get_text("time_changed", lang, time=new_time)
        )
    
    elif data.startswith("settz_"):
        timezone = data.replace("settz_", "")
        db.update_user(user_id, timezone=timezone)
        
        # Reschedule
        user = db.get_user(user_id)
        schedule_user_daily_verb(context.application, user)
        
        await query.edit_message_text(get_text("timezone_changed", lang))


def get_time_keyboard_settings():
    """Time keyboard for settings (different callback)."""
    keyboard = []
    row = []
    for i, t in enumerate(TIME_OPTIONS):
        row.append(InlineKeyboardButton(t, callback_data=f"settime_{t}"))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    return InlineKeyboardMarkup(keyboard)


def schedule_user_daily_verb(app: Application, user: dict):
    """Schedule daily verb for a user."""
    if not user['is_active'] or not user['onboarding_complete']:
        return
    
    job_name = f"daily_{user['user_id']}"
    
    # Remove existing job if any
    current_jobs = app.job_queue.get_jobs_by_name(job_name)
    for job in current_jobs:
        job.schedule_removal()
    
    # Parse time
    hour, minute = map(int, user['daily_time'].split(':'))
    user_tz = ZoneInfo(user['timezone'])
    
    # Schedule new job
    app.job_queue.run_daily(
        send_daily_verb_job,
        time=time(hour=hour, minute=minute, tzinfo=user_tz),
        data={'user_id': user['user_id']},
        name=job_name
    )
    logger.info(f"Scheduled daily verb for user {user['user_id']} at {user['daily_time']} {user['timezone']}")


async def send_daily_verb_job(context: ContextTypes.DEFAULT_TYPE):
    """Job callback for sending daily verb."""
    user_id = context.job.data['user_id']
    user = db.get_user(user_id)
    
    if user and user['is_active']:
        await send_verb_to_user(context.bot, user_id)


async def post_init(app: Application):
    """Set up bot commands menu and schedule jobs after bot starts."""
    # Set up the command menu
    commands = [
        BotCommand("start", "Set up or reset preferences"),
        BotCommand("verb", "Get a random verb"),
        BotCommand("quiz", "Test yourself"),
        BotCommand("stats", "See your progress"),
        BotCommand("settings", "Change preferences"),
        BotCommand("help", "Show help message"),
    ]
    await app.bot.set_my_commands(commands)
    logger.info("Bot commands menu set up")
    
    # Schedule jobs for all existing users
    users = db.get_all_active_users()
    for user in users:
        schedule_user_daily_verb(app, user)
    logger.info(f"Scheduled daily verbs for {len(users)} users")


def main():
    """Start the bot."""
    # Initialize database
    db.init_db()
    
    # Create application
    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()
    
    # Add command handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("verb", verb_command))
    app.add_handler(CommandHandler("quiz", quiz_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("settings", settings_command))
    app.add_handler(CommandHandler("help", help_command))
    
    # Callback handlers
    app.add_handler(CallbackQueryHandler(handle_quiz_callback, pattern=r"^quiz_"))
    app.add_handler(CallbackQueryHandler(handle_settings_callback, pattern=r"^(settings_|setlang_|settime_|settz_)"))
    app.add_handler(CallbackQueryHandler(handle_onboarding_callback, pattern=r"^(lang_|tz_|time_)"))
    
    # Handle non-command messages
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_unknown_message))
    
    # Handle file uploads (photos, documents, audio, video, etc.)
    app.add_handler(MessageHandler(
        filters.PHOTO | filters.Document.ALL | filters.AUDIO | filters.VIDEO | filters.VOICE | filters.Sticker.ALL,
        handle_file_upload
    ))
    
    # Start the bot
    logger.info("Starting bot...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
