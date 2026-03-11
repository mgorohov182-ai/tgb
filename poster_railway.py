import asyncio
import os
import random
import logging
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from pathlib import Path

from pyrogram import Client
from pyrogram.errors import (
    FloodWait, RPCError, PeerIdInvalid, ChatWriteForbidden,
    ChatIdInvalid, ChannelInvalid, UsernameNotOccupied,
    InviteHashInvalid, UserAlreadyParticipant, UserNotParticipant,
    ChatAdminRequired, InviteRequestSent
)
from pyrogram.types import Chat, Dialog
from pyrogram.enums import ChatType

# =============== НАСТРОЙКИ ===============
API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH", "")
PHONE_NUMBER = os.environ.get("PHONE_NUMBER", "")
POSTS_PER_HOUR = int(os.environ.get("POSTS_PER_HOUR", 5))          # 5 сообщений в час
SEARCH_INTERVAL_HOURS = int(os.environ.get("SEARCH_INTERVAL", 6))  # Поиск каждые 6 часов
MIN_MEMBERS = int(os.environ.get("MIN_MEMBERS", 100))              # Минимум участников
MAX_GROUPS_PER_SEARCH = int(os.environ.get("MAX_GROUPS_PER_SEARCH", 10))  # Сколько групп добавлять за раз
USE_PROXY = os.environ.get("USE_PROXY", "false").lower() == "true"  # Использовать прокси?
PROXY_CONFIG = {
    "scheme": os.environ.get("PROXY_SCHEME", "socks5"),
    "hostname": os.environ.get("PROXY_HOST", ""),
    "port": int(os.environ.get("PROXY_PORT", 0)),
    "username": os.environ.get("PROXY_USER", None),
    "password": os.environ.get("PROXY_PASS", None)
} if USE_PROXY else None

# Файлы
GROUPS_FILE = "groups.txt"                 # Ручной список (опционально)
ACTIVE_GROUPS_FILE = "active_groups.json"  # Активные группы с метаданными
MESSAGE_FILE = "message.txt"               # Базовый текст
SESSION_NAME = "my_account"
LOG_FILE = "bot.log"

# Поисковые запросы
SEARCH_QUERIES = [
    "#роблокс", "#роблоксскрипты", "#роблоксчиты", "#роблоксобщение",
    "#roblox", "#robloxscripts", "#robloxhacks", "#robloxexploits",
    "roblox scripts", "roblox hack", "роблокс скрипты", "роблокс читы"
]

# =============== НАСТРОЙКИ ЛОГИРОВАНИЯ ===============
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("NovaBot")

# =============== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ===============

def load_base_message() -> Optional[str]:
    """Загружает базовый текст сообщения"""
    path = Path(MESSAGE_FILE)
    if not path.exists():
        logger.error(f"Файл {MESSAGE_FILE} не найден!")
        return None
    return path.read_text(encoding='utf-8').strip()

def load_active_groups() -> Dict[str, Dict]:
    """Загружает активные группы из JSON-файла"""
    path = Path(ACTIVE_GROUPS_FILE)
    if not path.exists():
        return {}
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Ошибка загрузки активных групп: {e}")
        return {}

def save_active_groups(groups: Dict[str, Dict]):
    """Сохраняет активные группы в JSON-файл"""
    with open(ACTIVE_GROUPS_FILE, 'w', encoding='utf-8') as f:
        json.dump(groups, f, ensure_ascii=False, indent=2)
    logger.info(f"Сохранено {len(groups)} активных групп")

def load_manual_groups() -> List[str]:
    """Загружает ручные группы из groups.txt (если есть)"""
    path = Path(GROUPS_FILE)
    if not path.exists():
        return []
    with open(path, 'r', encoding='utf-8') as f:
        return [line.strip() for line in f if line.strip()]

def normalize_chat_id(raw_id) -> List[str]:
    """Преобразует ID в список возможных строковых представлений"""
    raw = str(raw_id).strip()
    candidates = [raw]
    # Если число с минусом, пробуем разные вариации
    if raw.lstrip('-').isdigit():
        num = int(raw)
        if num < 0 and not raw.startswith('-100'):
            candidates.append(f"-100{abs(num)}")
        if raw.startswith('-100'):
            candidates.append(str(num))  # исходный
            rest = raw[4:]
            if rest.lstrip('-').isdigit():
                candidates.append(rest)
    return list(set(candidates))

def generate_message_variation(base: str) -> str:
    """Генерирует вариацию сообщения с эмодзи и небольшими изменениями"""
    emojis = ["🔥", "🚀", "💎", "⚡️", "🎯", "💯", "👑", "⭐️", "✨", "🎮", "🕹️", "🤖", "👾"]
    templates = [
        "{base}",
        "🔥 {base}",
        "{base} 🔥",
        "⚡️ СРОЧНО: {base}",
        "🚀 {base} 🚀",
        "ВНИМАНИЕ! {base}",
        "{base}\n\nПрисоединяйся! 👇",
        "Только сегодня: {base}",
        "💎 ЭКСКЛЮЗИВ: {base}"
    ]
    template = random.choice(templates)
    message = template.format(base=base)
    # Добавляем случайные эмодзи в конец
    if random.random() < 0.8:
        num = random.randint(1, 3)
        message += " " + " ".join(random.choices(emojis, k=num))
    return message

# =============== ОСНОВНОЙ КЛАСС БОТА ===============

class NovaBot:
    def __init__(self):
        self.app = None
        self.active_groups = {}
        self.base_message = load_base_message()
        self.interval = 3600 // POSTS_PER_HOUR  # интервал между циклами
        self.search_interval = SEARCH_INTERVAL_HOURS * 3600
        self.last_search_time = 0

    async def start(self):
        """Запуск клиента"""
        logger.info("Запуск NovaBot...")
        logger.info(f"Настройки: {POSTS_PER_HOUR} сообщений/час, интервал {self.interval}с")
        logger.info(f"Поиск групп каждые {SEARCH_INTERVAL_HOURS}ч, мин. участников: {MIN_MEMBERS}")

        if not all([API_ID, API_HASH, PHONE_NUMBER]):
            logger.error("Не заданы API_ID, API_HASH или PHONE_NUMBER")
            return False

        client_kwargs = {
            "name": SESSION_NAME,
            "api_id": API_ID,
            "api_hash": API_HASH,
            "phone_number": PHONE_NUMBER,
            "workdir": "./"
        }
        if USE_PROXY and PROXY_CONFIG["hostname"]:
            client_kwargs["proxy"] = PROXY_CONFIG

        self.app = Client(**client_kwargs)
        await self.app.start()
        logger.info("✅ Авторизация успешна")
        return True

    async def stop(self):
        """Остановка клиента"""
        if self.app:
            await self.app.stop()
            logger.info("Бот остановлен")

    async def search_and_join_groups(self):
        """Поиск новых групп по хештегам и вступление в них"""
        logger.info("🔍 Начинаю поиск новых групп...")
        found = 0

        for query in SEARCH_QUERIES:
            try:
                logger.info(f"   Поиск по запросу: {query}")
                async for dialog in self.app.search_global(query, limit=50):
                    # Пропускаем, если это не группа/супергруппа
                    if dialog.chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
                        continue

                    chat_id = str(dialog.chat.id)
                    # Проверяем, не в активных ли уже
                    if chat_id in self.active_groups:
                        continue

                    # Получаем полную информацию о чате
                    try:
                        full_chat = await self.app.get_chat(chat_id)
                    except Exception as e:
                        logger.debug(f"Не удалось получить информацию о {chat_id}: {e}")
                        continue

                    # Проверяем количество участников
                    members = getattr(full_chat, 'members_count', 0)
                    if members < MIN_MEMBERS:
                        logger.info(f"      ⏩ {full_chat.title} — участников {members} < {MIN_MEMBERS}, пропускаем")
                        continue

                    # Пытаемся вступить, если ещё не участник
                    try:
                        await self.app.join_chat(chat_id)
                        logger.info(f"      ✅ Вступил в группу: {full_chat.title} (ID: {chat_id}, участников: {members})")
                    except UserAlreadyParticipant:
                        logger.info(f"      ✅ Уже участник: {full_chat.title}")
                    except (InviteHashInvalid, ChatAdminRequired, InviteRequestSent) as e:
                        logger.warning(f"      ❌ Не удалось вступить в {full_chat.title}: {e}")
                        continue
                    except Exception as e:
                        logger.warning(f"      ❌ Ошибка при вступлении в {full_chat.title}: {e}")
                        continue

                    # Добавляем в активные
                    self.active_groups[chat_id] = {
                        "title": full_chat.title,
                        "members": members,
                        "added": datetime.now().isoformat(),
                        "last_error": None,
                        "active": True
                    }
                    found += 1
                    if found >= MAX_GROUPS_PER_SEARCH:
                        break

                    # Задержка между группами
                    await asyncio.sleep(random.uniform(5, 10))

            except FloodWait as e:
                logger.warning(f"⚠️ Флуд при поиске, ждём {e.value}с")
                await asyncio.sleep(e.value)
            except Exception as e:
                logger.error(f"Ошибка при поиске по запросу {query}: {e}")

            if found >= MAX_GROUPS_PER_SEARCH:
                break

        if found:
            save_active_groups(self.active_groups)
            logger.info(f"✅ Добавлено {found} новых групп")
        else:
            logger.info("Новых групп не найдено")

    async def send_to_group(self, chat_id: str, message: str) -> Tuple[bool, Optional[str]]:
        """Отправляет сообщение в конкретную группу, возвращает (успех, ошибка)"""
        candidates = normalize_chat_id(chat_id)
        last_error = None

        for cid in candidates:
            try:
                # Рандомная задержка перед отправкой (2-7 секунд)
                await asyncio.sleep(random.uniform(2, 7))
                await self.app.send_message(cid, message)
                return True, None
            except (PeerIdInvalid, ChatIdInvalid, ChannelInvalid, UsernameNotOccupied) as e:
                last_error = f"Неверный ID: {e}"
                continue
            except ChatWriteForbidden as e:
                last_error = f"Нет прав на отправку: {e}"
                break  # права не зависят от формата ID
            except FloodWait as e:
                logger.warning(f"⚠️ Флуд в {chat_id}, ждём {e.value}с")
                await asyncio.sleep(e.value)
                continue
            except RPCError as e:
                last_error = f"RPC ошибка: {e}"
                continue
            except Exception as e:
                last_error = f"Неизвестная ошибка: {e}"
                continue

        return False, last_error

    async def distribute_messages(self):
        """Основной цикл рассылки по всем активным группам"""
        # Загружаем активные группы (обновляем из файла, если были изменения)
        self.active_groups = load_active_groups()

        # Добавляем ручные группы из groups.txt (если их нет в активных)
        for g in load_manual_groups():
            if g not in self.active_groups:
                self.active_groups[g] = {
                    "title": "manual",
                    "members": 0,
                    "added": datetime.now().isoformat(),
                    "last_error": None,
                    "active": True
                }

        if not self.active_groups:
            logger.warning("Нет активных групп для рассылки")
            return

        # Перемешиваем группы для случайного порядка
        group_ids = list(self.active_groups.keys())
        random.shuffle(group_ids)

        logger.info(f"📨 Начинаю рассылку в {len(group_ids)} групп...")

        for gid in group_ids:
            if not self.active_groups[gid].get("active", True):
                continue  # пропускаем неактивные

            message = generate_message_variation(self.base_message)
            success, error = await self.send_to_group(gid, message)

            if success:
                logger.info(f"✅ Отправлено в {self.active_groups[gid].get('title', gid)} ({gid})")
                # Сбрасываем счётчик ошибок
                self.active_groups[gid]["last_error"] = None
                self.active_groups[gid]["active"] = True
            else:
                logger.error(f"❌ Ошибка в {self.active_groups[gid].get('title', gid)} ({gid}): {error}")
                self.active_groups[gid]["last_error"] = error
                # Если ошибка критическая (нет прав, неверный ID), помечаем как неактивную
                if error and ("прав" in error or "ID" in error):
                    self.active_groups[gid]["active"] = False
                    logger.warning(f"   Группа {gid} помечена как неактивная")

            # Сохраняем обновлённый статус после каждой группы
            save_active_groups(self.active_groups)

            # Базовая задержка между группами (10-20 секунд)
            await asyncio.sleep(random.uniform(10, 20))

        logger.info("✅ Рассылка завершена")

    async def run(self):
        """Главный цикл работы бота"""
        if not await self.start():
            return

        # Первоначальная загрузка групп
        self.active_groups = load_active_groups()
        logger.info(f"Загружено {len(self.active_groups)} активных групп из файла")

        # Счётчик для периодического поиска
        loop_counter = 0
        cycles_per_search = int(self.search_interval // self.interval)

        while True:
            try:
                # Рассылка
                await self.distribute_messages()

                loop_counter += 1

                # Проверяем, не пора ли искать новые группы
                if loop_counter % cycles_per_search == 0:
                    await self.search_and_join_groups()

                logger.info(f"⏳ Следующая отправка через {self.interval} секунд...")
                await asyncio.sleep(self.interval)

            except KeyboardInterrupt:
                logger.info("🛑 Остановка по команде пользователя")
                break
            except Exception as e:
                logger.exception(f"❌ Критическая ошибка: {e}")
                logger.info("⏳ Перезапуск через 60 секунд...")
                await asyncio.sleep(60)

        await self.stop()

# =============== ТОЧКА ВХОДА ===============

if __name__ == "__main__":
    bot = NovaBot()
    asyncio.run(bot.run())


