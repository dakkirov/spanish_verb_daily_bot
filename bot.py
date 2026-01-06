import asyncio
import logging
import random
from datetime import datetime, time
from zoneinfo import ZoneInfo

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, 
    CommandHandler, 
    CallbackQueryHandler,
    ContextTypes,
    JobQueue
)

import database as db
from verbs import VERBS, get_verb_by_index, get_random_verb, get_verb_count

# Bot token
BOT_TOKEN = "8591777399:AAGL3N481GjilQVUno1VdTEjSiK8fTIFIvI"

# Logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Supported languages for translation
LANGUAGES = {
    'english': '🇬🇧 English',
    'portuguese': '🇧🇷 Portuguese', 
    'french': '🇫🇷 French',
    'italian': '🇮🇹 Italian',
    'german': '🇩🇪 German'
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
    'UTC': '🌍 UTC'
}

# Time options
TIME_OPTIONS = ['07:00', '08:00', '09:00', '10:00', '12:00', '18:00', '20:00', '21:00']


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
        # User already set up
        await update.message.reply_text(
            f"Welcome back! 🎉\n\n"
            f"Use /verb to get a random verb\n"
            f"Use /quiz to test yourself\n"
            f"Use /settings to change your preferences\n"
            f"Use /stats to see your progress"
        )
        return
    
    # Create or reset user
    db.create_user(user.id, user.username)
    db.update_user(user.id, onboarding_step='language', onboarding_complete=0)
    
    # Start onboarding - language selection
    await update.message.reply_text(
        "Welcome! 🇦🇷 I'll send you an Argentinian Spanish verb every day.\n\n"
        "Let's set things up!\n\n"
        "<b>What language should I translate verbs to?</b>",
        parse_mode='HTML',
        reply_markup=get_language_keyboard()
    )


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
        
        await query.edit_message_text(
            f"Great! I'll translate verbs to {LANGUAGES[language]}.\n\n"
            f"<b>What's your timezone?</b>",
            parse_mode='HTML',
            reply_markup=get_timezone_keyboard()
        )
    
    elif data.startswith('tz_'):
        # Timezone selected
        timezone = data.replace('tz_', '')
        db.update_user(user_id, timezone=timezone, onboarding_step='time')
        
        await query.edit_message_text(
            f"<b>What time should I send your daily verb?</b>\n\n"
            f"(Time in your selected timezone)",
            parse_mode='HTML',
            reply_markup=get_time_keyboard()
        )
    
    elif data.startswith('time_'):
        # Time selected - onboarding complete!
        daily_time = data.replace('time_', '')
        db.update_user(user_id, daily_time=daily_time, onboarding_complete=1, onboarding_step='done')
        
        user = db.get_user(user_id)
        
        # Schedule the daily job for this user
        schedule_user_daily_verb(context.application, user)
        
        await query.edit_message_text(
            f"✅ <b>You're all set!</b>\n\n"
            f"📚 Translation: {LANGUAGES[user['language']]}\n"
            f"🕐 Daily verb at: {daily_time}\n"
            f"🌍 Timezone: {user['timezone']}\n\n"
            f"<b>Commands:</b>\n"
            f"/verb - Get a random verb now\n"
            f"/quiz - Test yourself on recent verbs\n"
            f"/stats - See your progress\n"
            f"/settings - Change your preferences\n\n"
            f"Here's your first verb! 👇",
            parse_mode='HTML'
        )
        
        # Send first verb
        await send_verb_to_user(context.application.bot, user_id)


async def verb_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /verb command - send a random verb."""
    user_id = update.effective_user.id
    user = db.get_user(user_id)
    
    if not user or not user['onboarding_complete']:
        await update.message.reply_text(
            "Please complete setup first! Use /start"
        )
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
    
    if not user or not user['onboarding_complete']:
        await update.message.reply_text("Please complete setup first! Use /start")
        return
    
    # Get recent verbs
    recent_indices = db.get_recent_verbs(user_id, limit=10)
    
    if len(recent_indices) < 2:
        await update.message.reply_text(
            "You need to learn more verbs first! 📚\n"
            "Use /verb to get more verbs, then come back for the quiz."
        )
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
            f"🧠 <b>Quiz Time!</b>\n\n"
            f"What does <b>{quiz_verb['infinitive']}</b> mean?",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    else:
        # Ask for conjugation
        tense = random.choice(['presente', 'pasado', 'futuro'])
        pronoun = random.choice(['yo', 'vos', 'él/ella'])
        correct_answer = quiz_verb[tense][pronoun]
        
        # Get wrong answers
        other_indices = [i for i in range(get_verb_count()) if i != quiz_verb_index]
        wrong_indices = random.sample(other_indices, 3)
        wrong_answers = [get_verb_by_index(i)[tense][pronoun] for i in wrong_indices]
        
        all_answers = [correct_answer] + wrong_answers
        random.shuffle(all_answers)
        
        tense_names = {'presente': 'Present', 'pasado': 'Past', 'futuro': 'Future'}
        
        keyboard = []
        for i, answer in enumerate(all_answers):
            letter = chr(65 + i)
            is_correct = 1 if answer == correct_answer else 0
            keyboard.append([InlineKeyboardButton(
                f"{letter}) {answer}",
                callback_data=f"quiz_{quiz_verb_index}_conjugation_{is_correct}"
            )])
        
        await update.message.reply_text(
            f"🧠 <b>Quiz Time!</b>\n\n"
            f"<b>{quiz_verb['infinitive'].upper()}</b>\n\n"
            f"What is the <b>{tense_names[tense]}</b> tense for <b>{pronoun}</b>?",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )


async def handle_quiz_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle quiz answer."""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    parts = query.data.split('_')
    # quiz_{verb_index}_{type}_{is_correct}
    verb_index = int(parts[1])
    question_type = parts[2]
    is_correct = parts[3] == '1'
    
    # Record result
    db.record_quiz_result(user_id, verb_index, question_type, is_correct)
    
    if is_correct:
        await query.edit_message_text(
            "✅ <b>Correct!</b> Great job! 🎉\n\n"
            "Use /quiz for another question or /verb for a new verb.",
            parse_mode='HTML'
        )
    else:
        verb = get_verb_by_index(verb_index)
        user = db.get_user(user_id)
        translation = verb['translations'][user['language']]
        
        await query.edit_message_text(
            f"❌ <b>Not quite!</b>\n\n"
            f"<b>{verb['infinitive']}</b> = {translation}\n\n"
            f"Keep practicing! Use /quiz for another question.",
            parse_mode='HTML'
        )


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /stats command."""
    user_id = update.effective_user.id
    user = db.get_user(user_id)
    
    if not user:
        await update.message.reply_text("Please use /start first!")
        return
    
    stats = db.get_quiz_stats(user_id)
    sent_count = len(db.get_sent_verb_indices(user_id))
    
    await update.message.reply_text(
        f"📊 <b>Your Progress</b>\n\n"
        f"📚 Verbs learned: {sent_count}/{get_verb_count()}\n"
        f"🧠 Quiz attempts: {stats['total']}\n"
        f"✅ Correct answers: {stats['correct']}\n"
        f"📈 Success rate: {stats['percentage']}%",
        parse_mode='HTML'
    )


async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /settings command."""
    user_id = update.effective_user.id
    user = db.get_user(user_id)
    
    if not user:
        await update.message.reply_text("Please use /start first!")
        return
    
    keyboard = [
        [InlineKeyboardButton("🌐 Change Language", callback_data="settings_language")],
        [InlineKeyboardButton("🕐 Change Time", callback_data="settings_time")],
        [InlineKeyboardButton("🌍 Change Timezone", callback_data="settings_timezone")],
        [InlineKeyboardButton("⏸️ Pause Daily Verbs", callback_data="settings_pause")],
    ]
    
    await update.message.reply_text(
        f"⚙️ <b>Current Settings</b>\n\n"
        f"🌐 Language: {LANGUAGES[user['language']]}\n"
        f"🕐 Daily time: {user['daily_time']}\n"
        f"🌍 Timezone: {user['timezone']}\n"
        f"📬 Status: {'Active' if user['is_active'] else 'Paused'}\n\n"
        f"What would you like to change?",
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def handle_settings_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle settings changes."""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    data = query.data
    
    if data == "settings_language":
        await query.edit_message_text(
            "Select your new translation language:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(name, callback_data=f"setlang_{code}")]
                for code, name in LANGUAGES.items()
            ])
        )
    
    elif data == "settings_time":
        await query.edit_message_text(
            "Select your new daily time:",
            reply_markup=get_time_keyboard_settings()
        )
    
    elif data == "settings_timezone":
        await query.edit_message_text(
            "Select your timezone:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(name, callback_data=f"settz_{code}")]
                for code, name in TIMEZONES.items()
            ])
        )
    
    elif data == "settings_pause":
        user = db.get_user(user_id)
        new_status = 0 if user['is_active'] else 1
        db.update_user(user_id, is_active=new_status)
        
        status_text = "resumed" if new_status else "paused"
        await query.edit_message_text(
            f"✅ Daily verbs have been {status_text}!\n\n"
            f"Use /settings to change this anytime."
        )
    
    elif data.startswith("setlang_"):
        language = data.replace("setlang_", "")
        db.update_user(user_id, language=language)
        await query.edit_message_text(
            f"✅ Language changed to {LANGUAGES[language]}!\n\n"
            f"Use /settings to make more changes."
        )
    
    elif data.startswith("settime_"):
        new_time = data.replace("settime_", "")
        db.update_user(user_id, daily_time=new_time)
        
        # Reschedule
        user = db.get_user(user_id)
        schedule_user_daily_verb(context.application, user)
        
        await query.edit_message_text(
            f"✅ Daily time changed to {new_time}!\n\n"
            f"Use /settings to make more changes."
        )
    
    elif data.startswith("settz_"):
        timezone = data.replace("settz_", "")
        db.update_user(user_id, timezone=timezone)
        
        # Reschedule
        user = db.get_user(user_id)
        schedule_user_daily_verb(context.application, user)
        
        await query.edit_message_text(
            f"✅ Timezone changed!\n\n"
            f"Use /settings to make more changes."
        )


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
    """Schedule jobs for all existing users after bot starts."""
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
    
    # Add handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("verb", verb_command))
    app.add_handler(CommandHandler("quiz", quiz_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("settings", settings_command))
    
    # Callback handlers
    app.add_handler(CallbackQueryHandler(handle_quiz_callback, pattern=r"^quiz_"))
    app.add_handler(CallbackQueryHandler(handle_settings_callback, pattern=r"^(settings_|setlang_|settime_|settz_)"))
    app.add_handler(CallbackQueryHandler(handle_onboarding_callback, pattern=r"^(lang_|tz_|time_)"))
    
    # Start the bot
    logger.info("Starting bot...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
