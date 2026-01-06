# Spanish Verb Daily Bot 🇦🇷

A Telegram bot that sends you an Argentinian Spanish verb every day with conjugations (using vos/ustedes).

## Features

- **Daily verb delivery** at your chosen time
- **Personalized setup** - choose your translation language, timezone, and time
- **Argentinian Spanish** - uses vos conjugation and ustedes (no vosotros)
- **Quiz mode** - test yourself on recent verbs
- **Progress tracking** - see your stats

## Commands

- `/start` - Begin setup
- `/verb` - Get a random verb
- `/quiz` - Test yourself
- `/stats` - See your progress
- `/settings` - Change preferences

## Local Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Run the bot:
```bash
python bot.py
```

## Free Hosting Options

### Option 1: Railway (Recommended)

1. Create account at [railway.app](https://railway.app)
2. Click "New Project" → "Deploy from GitHub repo"
3. Connect your GitHub and push this code
4. Add environment variable: `BOT_TOKEN` = your token
5. Railway will auto-deploy!

**Procfile for Railway:**
```
worker: python bot.py
```

### Option 2: Render

1. Create account at [render.com](https://render.com)
2. New → Background Worker
3. Connect GitHub repo
4. Build command: `pip install -r requirements.txt`
5. Start command: `python bot.py`
6. Add environment variable: `BOT_TOKEN`

### Option 3: Fly.io (Free tier available)

1. Install flyctl: https://fly.io/docs/hands-on/install-flyctl/
2. Run:
```bash
fly launch
fly secrets set BOT_TOKEN=your_token_here
fly deploy
```

### Option 4: PythonAnywhere (Free tier)

1. Create account at [pythonanywhere.com](https://www.pythonanywhere.com)
2. Upload files via Files tab
3. Open Bash console and run:
```bash
pip install --user -r requirements.txt
python bot.py
```
Note: Free tier has limitations on always-on tasks.

## File Structure

```
spanish_verb_bot/
├── bot.py           # Main bot code
├── verbs.py         # Verb database (30 verbs)
├── database.py      # SQLite database for user preferences
├── requirements.txt # Dependencies
└── README.md        # This file
```

## Adding More Verbs

Edit `verbs.py` and add new verbs following the existing format:

```python
{
    "infinitive": "verb",
    "definition": "Spanish definition",
    "translations": {
        "english": "...",
        "portuguese": "...",
        # etc
    },
    "presente": {
        "yo": "...",
        "vos": "...",
        # etc
    },
    # pasado, futuro...
}
```

## Security Note

⚠️ Never share your bot token publicly! If exposed:
1. Go to @BotFather on Telegram
2. Send `/revoke`
3. Select your bot
4. Get a new token

Then update your hosting environment variable.
