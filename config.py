import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Telegram API
    API_ID = int(os.getenv("API_ID", 0))
    API_HASH = os.getenv("API_HASH", "")
    PHONE_NUMBER = os.getenv("PHONE_NUMBER", "")
    
    # Файлы
    SESSION_NAME = "my_account"
    MESSAGE_FILE = "message.txt"
    QUERIES_FILE = "data/queries.txt"
    ACTIVE_GROUPS_FILE = "data/active_groups.json"
    BLACKLIST_FILE = "data/blacklist.json"
    STATS_FILE = "data/stats.json"
    
    # Настройки рассылки
    POSTS_PER_HOUR = 3  # сообщений в час (безопасно)
    MIN_MEMBERS = 50     # минимальное количество участников
    MAX_GROUPS = 100     # максимум групп для рассылки
    
    # Настройки поиска
    SEARCH_INTERVAL_HOURS = 6
    MAX_GROUPS_PER_SEARCH = 5
    
    # Настройки прокси (опционально)
    USE_PROXY = False
    PROXY = {
        "scheme": "socks5",
        "hostname": "",
        "port": 0,
        "username": None,
        "password": None
    }
    
    # Для Google поиска
    GOOGLE_SEARCH_ENABLED = True
    GOOGLE_SEARCH_QUERIES = [
        "telegram group roblox",
        "telegram chat roblox scripts",
        "роблокс чат телеграм",
        "роблокс группа телеграм"
    ]
    
    @classmethod
    def validate(cls):
        errors = []
        if not cls.API_ID:
            errors.append("API_ID не задан")
        if not cls.API_HASH:
            errors.append("API_HASH не задан")
        if not cls.PHONE_NUMBER:
            errors.append("PHONE_NUMBER не задан")
        return errors