import sqlite3
import json
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent / "bot_data.db"


def get_connection():
    """Get database connection."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Initialize the database with required tables."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            language TEXT DEFAULT 'english',
            timezone TEXT DEFAULT 'UTC',
            daily_time TEXT DEFAULT '09:00',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_active INTEGER DEFAULT 1,
            onboarding_complete INTEGER DEFAULT 0,
            onboarding_step TEXT DEFAULT 'language'
        )
    ''')
    
    # Sent verbs table (to track which verbs were sent to each user)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sent_verbs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            verb_index INTEGER,
            sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    ''')
    
    # Quiz results table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS quiz_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            verb_index INTEGER,
            question_type TEXT,
            is_correct INTEGER,
            answered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    ''')
    
    conn.commit()
    conn.close()


def get_user(user_id: int) -> dict | None:
    """Get user by ID."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def create_user(user_id: int, username: str = None) -> dict:
    """Create a new user."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        'INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)',
        (user_id, username)
    )
    conn.commit()
    conn.close()
    return get_user(user_id)


def update_user(user_id: int, **kwargs) -> dict:
    """Update user fields."""
    conn = get_connection()
    cursor = conn.cursor()
    
    valid_fields = ['language', 'timezone', 'daily_time', 'is_active', 
                    'onboarding_complete', 'onboarding_step']
    
    updates = {k: v for k, v in kwargs.items() if k in valid_fields}
    
    if updates:
        set_clause = ', '.join(f'{k} = ?' for k in updates.keys())
        values = list(updates.values()) + [user_id]
        cursor.execute(f'UPDATE users SET {set_clause} WHERE user_id = ?', values)
        conn.commit()
    
    conn.close()
    return get_user(user_id)


def get_all_active_users() -> list:
    """Get all active users with completed onboarding."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        'SELECT * FROM users WHERE is_active = 1 AND onboarding_complete = 1'
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def record_sent_verb(user_id: int, verb_index: int):
    """Record that a verb was sent to a user."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        'INSERT INTO sent_verbs (user_id, verb_index) VALUES (?, ?)',
        (user_id, verb_index)
    )
    conn.commit()
    conn.close()


def get_sent_verb_indices(user_id: int) -> list:
    """Get list of verb indices already sent to user."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        'SELECT DISTINCT verb_index FROM sent_verbs WHERE user_id = ?',
        (user_id,)
    )
    rows = cursor.fetchall()
    conn.close()
    return [row['verb_index'] for row in rows]


def get_recent_verbs(user_id: int, limit: int = 5) -> list:
    """Get recently sent verbs for quiz."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        '''SELECT verb_index FROM sent_verbs 
           WHERE user_id = ? 
           ORDER BY sent_at DESC 
           LIMIT ?''',
        (user_id, limit)
    )
    rows = cursor.fetchall()
    conn.close()
    return [row['verb_index'] for row in rows]


def record_quiz_result(user_id: int, verb_index: int, question_type: str, is_correct: bool):
    """Record a quiz answer."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        '''INSERT INTO quiz_results (user_id, verb_index, question_type, is_correct) 
           VALUES (?, ?, ?, ?)''',
        (user_id, verb_index, question_type, int(is_correct))
    )
    conn.commit()
    conn.close()


def get_quiz_stats(user_id: int) -> dict:
    """Get quiz statistics for a user."""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute(
        '''SELECT 
            COUNT(*) as total,
            SUM(is_correct) as correct
           FROM quiz_results WHERE user_id = ?''',
        (user_id,)
    )
    row = cursor.fetchone()
    conn.close()
    
    total = row['total'] or 0
    correct = row['correct'] or 0
    
    return {
        'total': total,
        'correct': correct,
        'percentage': round(correct / total * 100, 1) if total > 0 else 0
    }


# Initialize DB when module is imported
init_db()
