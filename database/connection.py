import psycopg2
from psycopg2.extras import RealDictCursor

def get_db_connection():
    try:
        conn = psycopg2.connect(
            host="localhost",
            database="safeconnect_db",
            user="postgres",
            password="chethansm@123",
            port="5432",
            cursor_factory=RealDictCursor
        )

        return conn

    except Exception as e:
        print("Database Connection Error:", e)
        return None