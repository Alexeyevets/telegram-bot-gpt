import sqlite3

db_path = 'users.db'

sql_query = '''
PRAGMA foreign_keys = 0;

CREATE TABLE sqlitestudio_temp_table AS SELECT * FROM users;

DROP TABLE users;

CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    nickname TEXT NOT NULL,
    username TEXT,
    request_count INTEGER DEFAULT 0,
    last_reset TEXT
);

INSERT INTO users (
    id,
    nickname,
    username,
    request_count,
    last_reset
)
SELECT id,
       nickname,
       username,
       request_count,
       last_reset
FROM sqlitestudio_temp_table;

DROP TABLE sqlitestudio_temp_table;

PRAGMA foreign_keys = 1;
'''

# Функция для выполнения SQL-запроса
def execute_sql_query(db_path, query):
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.executescript(query)
        conn.commit()
        conn.close()
        return "SQL-запрос выполнен успешно."
    except Exception as e:
        return f"Произошла ошибка: {e}"

result = execute_sql_query(db_path, sql_query)
print(result)
