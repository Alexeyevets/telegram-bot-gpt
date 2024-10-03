import sqlite3
from sqlite3 import Error
import datetime

DATABASE = "users.db"

def create_connection():
    """Создание подключения к базе данных SQLite."""
    conn = None
    try:
        conn = sqlite3.connect(DATABASE)
    except Error as e:
        print(e)
    return conn

def create_table():
    """Создание таблицы пользователей."""
    conn = create_connection()
    try:
        sql_create_users_table = """ CREATE TABLE IF NOT EXISTS users (
                                        id integer PRIMARY KEY,
                                        nickname text NOT NULL,
                                        username text,
                                        request_count integer DEFAULT 0,
                                        last_reset text,
                                        blocked text DEFAULT 'Yes'
                                    ); """
        conn.execute(sql_create_users_table)
        conn.commit()
    except Error as e:
        print(e)
    finally:
        if conn:
            conn.close()

def add_column_if_not_exists():
    """Добавление недостающих колонок в таблицу пользователей."""
    conn = create_connection()
    try:
        cur = conn.cursor()
        cur.execute("PRAGMA table_info(users);")
        columns = [col[1] for col in cur.fetchall()]
        if 'request_count' not in columns:
            cur.execute("ALTER TABLE users ADD COLUMN request_count INTEGER DEFAULT 0;")
        if 'last_reset' not in columns:
            cur.execute("ALTER TABLE users ADD COLUMN last_reset TEXT;")
        if 'blocked' not in columns:
            cur.execute("ALTER TABLE users ADD COLUMN blocked TEXT DEFAULT 'Yes';")
        conn.commit()
    except Error as e:
        print(e)
    finally:
        if conn:
            conn.close()

def add_user(user_id, nickname, username):
    """Добавление пользователя в базу данных."""
    conn = create_connection()
    try:
        sql = ''' INSERT INTO users(id, nickname, username, last_reset, blocked)
                  VALUES(?, ?, ?, ?, 'Yes') '''
        cur = conn.cursor()
        cur.execute(sql, (user_id, nickname, username, datetime.date.today().isoformat()))
        conn.commit()
    except Error as e:
        print(e)
    finally:
        if conn:
            conn.close()

def remove_user(user_id):
    """Удаление пользователя из базы данных."""
    conn = create_connection()
    try:
        sql = 'DELETE FROM users WHERE id=?'
        cur = conn.cursor()
        cur.execute(sql, (user_id,))
        conn.commit()
    except Error as e:
        print(e)
    finally:
        if conn:
            conn.close()

def get_all_users():
    """Получение всех пользователей из базы данных."""
    conn = create_connection()
    users = []
    try:
        sql = 'SELECT * FROM users'
        cur = conn.cursor()
        cur.execute(sql)
        rows = cur.fetchall()
        for row in rows:
            users.append({"id": row[0], "nickname": row[1], "username": row[2], "request_count": row[3], "last_reset": row[4],"blocked": row[5]})
    except Error as e:
        print(e)
    finally:
        if conn:
            conn.close()
    return users

def get_user_by_username(username):
    """Получение пользователя по username."""
    conn = create_connection()
    user = None
    try:
        sql = 'SELECT * FROM users WHERE username=?'
        cur = conn.cursor()
        cur.execute(sql, (username,))
        row = cur.fetchone()
        if row:
            user = {"id": row[0], "nickname": row[1], "username": row[2], "request_count": row[3], "last_reset": row[4], "blocked": row[5]}
    except Error as e:
        print(e)
    finally:
        if conn:
            conn.close()
    return user

def get_user_by_id(user_id):
    """Получение пользователя по ID."""
    conn = create_connection()
    user = None
    try:
        sql = 'SELECT * FROM users WHERE id=?'
        cur = conn.cursor()
        cur.execute(sql, (user_id,))
        row = cur.fetchone()
        if row:
            user = {"id": row[0], "nickname": row[1], "username": row[2], "request_count": row[3], "last_reset": row[4], "blocked": row[5]}
    except Error as e:
        print(e)
    finally:
        if conn:
            conn.close()
    return user

def increment_request_count(user_id):
    """Увеличение количества запросов пользователя."""
    conn = create_connection()
    try:
        sql = 'UPDATE users SET request_count = request_count + 1 WHERE id=?'
        cur = conn.cursor()
        cur.execute(sql, (user_id,))
        conn.commit()
    except Error as e:
        print(e)
    finally:
        if conn:
            conn.close()

def reset_request_counts():
    """Обнуление количества запросов для всех пользователей."""
    conn = create_connection()
    today = datetime.date.today().isoformat()
    try:
        sql = 'UPDATE users SET request_count = 0, last_reset = ?'
        cur = conn.cursor()
        cur.execute(sql, (today,))
        conn.commit()
    except Error as e:
        print(e)
    finally:
        if conn:
            conn.close()

def check_and_reset_request_counts():
    """Проверка и обнуление количества запросов, если это необходимо."""
    conn = create_connection()
    today = datetime.date.today().isoformat()
    try:
        sql = 'SELECT id, last_reset FROM users'
        cur = conn.cursor()
        cur.execute(sql)
        rows = cur.fetchall()
        for row in rows:
            if row[1] != today:
                reset_request_counts()
                break
    except Error as e:
        print(e)
    finally:
        if conn:
            conn.close()

def block_user(user_id):
    """Блокировка пользователя."""
    conn = create_connection()
    try:
        sql = "UPDATE users SET blocked = 'No' WHERE id=?"
        cur = conn.cursor()
        cur.execute(sql, (user_id,))
        conn.commit()
    except Error as e:
        print(e)
    finally:
        if conn:
            conn.close()

def unblock_user(user_id):
    """Разблокировка пользователя."""
    conn = create_connection()
    try:
        sql = "UPDATE users SET blocked = 'Yes' WHERE id=?"
        cur = conn.cursor()
        cur.execute(sql, (user_id,))
        conn.commit()
    except Error as e:
        print(e)
    finally:
        if conn:
            conn.close()

def is_user_blocked(user_id):
    """Проверка, заблокирован ли пользователь."""
    user = get_user_by_id(user_id)
    return user and user['blocked'] == 'No'

create_table()
add_column_if_not_exists()
