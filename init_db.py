from database.models import init_db

if __name__ == "__main__":
    init_db()
    print("Database initialized: users, chat_sessions, chat_messages tables created.")
