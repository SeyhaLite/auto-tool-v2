import psycopg
from psycopg.rows import RealDictRow
from psycopg.types.json import Jsonb
import logging
from . import config

logger = logging.getLogger(__name__)

def db_query(query, params=(), fetch_one=False, commit=False):
    """General purpose DB helper function using psycopg."""
    try:
        # Use a context manager for the connection
        with psycopg.connect(config.DATABASE_URL) as conn:
            # Use a context manager for the cursor
            # RealDictRow makes results behave like dictionaries (e.g., row['user_id'])
            with conn.cursor(row_factory=RealDictRow) as cursor:
                cursor.execute(query, params)
                
                result = None
                if commit:
                    conn.commit()
                    # Try to get last inserted ID (less reliable than in SQLite)
                    # For a robust "returning id", the query itself should change.
                    # For our purposes, we'll assume commit=True is for inserts/updates
                    result = None # PostgreSQL commit doesn't return lastrowid simply
                else:
                    result = cursor.fetchone() if fetch_one else cursor.fetchall()
                    
                return result
    except Exception as e:
        logger.error(f"Database error executing query: {query} \nParams: {params} \nError: {e}", exc_info=True)
        # Re-raise the exception to be handled by the caller
        raise

def init_db():
    """Initializes the PostgreSQL database tables."""
    create_users_table = """
        CREATE TABLE IF NOT EXISTS users (
            user_id BIGINT PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            is_admin BOOLEAN DEFAULT FALSE,
            is_banned BOOLEAN DEFAULT FALSE,
            banned_until TIMESTAMP,
            joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """
    
    create_settings_table = """
        CREATE TABLE IF NOT EXISTS channels_settings (
            id SERIAL PRIMARY KEY,
            user_id BIGINT,
            source_channel_id BIGINT,
            target_channel_id BIGINT,
            custom_caption TEXT,
            remove_tags_caption BOOLEAN DEFAULT TRUE,
            is_active BOOLEAN DEFAULT TRUE,
            
            task_type TEXT DEFAULT 'new_messages', 
            start_message_id BIGINT DEFAULT 0,
            end_message_id BIGINT DEFAULT 0,
            current_message_id BIGINT DEFAULT 0,
            forward_every_n_posts INTEGER DEFAULT 1,
            interval_seconds INTEGER DEFAULT 10800,
            last_processed_message_id BIGINT DEFAULT 0,

            FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
        )
    """
    try:
        db_query(create_users_table, commit=True)
        db_query(create_settings_table, commit=True)
        logger.info("Database tables checked/created successfully.")
    except Exception as e:
        logger.critical(f"Failed to initialize database tables: {e}", exc_info=True)
        raise

# --- User DB Functions ---

def get_user(user_id):
    return db_query("SELECT * FROM users WHERE user_id = %s", (user_id,), fetch_one=True)

def add_user(user_id, username, first_name, last_name, is_admin=False):
    # Use PostgreSQL's "ON CONFLICT" to handle "INSERT OR IGNORE"
    query = """
        INSERT INTO users (user_id, username, first_name, last_name, is_admin) 
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (user_id) DO NOTHING
    """
    db_query(query, (user_id, username, first_name, last_name, is_admin), commit=True)

def update_user_ban_status(user_id, is_banned, banned_until=None):
    db_query("UPDATE users SET is_banned = %s, banned_until = %s WHERE user_id = %s",
             (is_banned, banned_until, user_id), commit=True)

def get_total_users():
    return db_query("SELECT COUNT(*) AS count FROM users", fetch_one=True)['count']

def get_all_users_ids():
    users = db_query("SELECT user_id FROM users WHERE is_banned = FALSE")
    return [user['user_id'] for user in users]

# --- Settings DB Functions ---

def get_user_forward_settings(user_id):
    return db_query("SELECT * FROM channels_settings WHERE user_id = %s", (user_id,))

def get_all_active_forward_settings():
    return db_query("SELECT * FROM channels_settings WHERE is_active = TRUE")

def get_setting_by_id(setting_id):
    return db_query("SELECT * FROM channels_settings WHERE id = %s", (setting_id,), fetch_one=True)

def add_forward_setting(data):
    # We must use "RETURNING id" to get the new ID in PostgreSQL
    query = """
        INSERT INTO channels_settings 
        (user_id, source_channel_id, target_channel_id, custom_caption, remove_tags_caption, 
         task_type, start_message_id, end_message_id, current_message_id, forward_every_n_posts, interval_seconds, is_active)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id
    """
    params = (
        data['user_id'], data['source_channel_id'], data['target_channel_id'], 
        data['custom_caption'], data['remove_tags_caption'], data['task_type'],
        data.get('start_message_id', 0), data.get('end_message_id', 0), 
        data.get('start_message_id', 0), # current_id starts at start_id
        data.get('forward_every_n_posts', 1), data['interval_seconds'], True
    )
    # Re-use db_query, but this time fetch_one=True and no commit (autocommit handles it)
    conn = psycopg.connect(config.DATABASE_URL)
    with conn.cursor(row_factory=RealDictRow) as cursor:
        cursor.execute(query, params)
        new_row = cursor.fetchone()
        conn.commit()
    
    return new_row['id'] if new_row else None


def update_setting_last_processed_id(setting_id, message_id):
    db_query("UPDATE channels_settings SET last_processed_message_id = %s WHERE id = %s", 
             (message_id, setting_id), commit=True)

def update_setting_current_id(setting_id, new_current_id):
    db_query("UPDATE channels_settings SET current_message_id = %s WHERE id = %s", 
             (new_current_id, setting_id), commit=True)

def update_setting_active(setting_id, is_active):
    db_query("UPDATE channels_settings SET is_active = %s WHERE id = %s", 
             (is_active, setting_id), commit=True)

def update_setting_caption(setting_id, new_caption):
    db_query("UPDATE channels_settings SET custom_caption = %s WHERE id = %s",
             (new_caption, setting_id), commit=True)

def update_setting_remove_tags(setting_id, new_status):
    db_query("UPDATE channels_settings SET remove_tags_caption = %s WHERE id = %s",
             (new_status, setting_id), commit=True)

def delete_setting_by_id(setting_id):
    db_query("DELETE FROM channels_settings WHERE id = %s", (setting_id,), commit=True)
