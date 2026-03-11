import asyncio
import os
import random
import re
from datetime import datetime
from typing import List, Union

from pyrogram import Client
from pyrogram.errors import (
    FloodWait, RPCError, PeerIdInvalid, ChatWriteForbidden,
    ChatIdInvalid, ChannelInvalid, UsernameNotOccupied,
    InviteHashExpired, InviteInvalid, UserAlreadyParticipant,
    ChatAdminRequired, ChatForbidden
)
from pyrogram.enums import ChatType
import time

# ===== НАСТРОЙКИ =====
API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH", "")
PHONE_NUMBER = os.environ.get("PHONE_NUMBER", "")
GROUPS_FILE = "groups.txt"               # Ручной список (если есть)
ACTIVE_GROUPS_FILE = "active_groups.txt"  # Сюда сохраняем пригодные группы
MESSAGE_FILE = "message.txt"
POSTS_PER_HOUR = int(os.environ.get("POSTS_PER_HOUR", 5))  # 5 в час
SESSION_NAME = "my_account"

# Настройки авто-поиска
SEARCH_QUERIES = [
    "#роблокс", "#роблоксскрипты", "#роблоксчиты", "#роблоксобщение",
    "#roblox", "#robloxscripts", "#robloxhacks", "#robloxexploits",
    "roblox scripts", "roblox hack", "роблокс скрипты"
]
MIN_MEMBERS = 100                         # Минимальное количество участников
MAX_GROUPS_TO_ADD_PER_SEARCH = 10         # Сколько новых групп добавить за раз
SEARCH_INTERVAL_HOURS = 6                  # Как часто искать новые группы
# =====================

INTERVAL_SECONDS = 3600 // POSTS_PER_HOUR  # интервал между циклами рассылки

# Эмодзи и вариации для текста
EMOJIS = ["🔥", "🚀", "💎", "⚡️", "🎯", "💯", "👑", "⭐️", "✨", "🎮", "🕹️", "🤖", "👾"]
TEXT_VARIATIONS = [
    "{}",
    "🔥 {}",
    "{} 🔥",
    "Внимание! {}",
    "⚡️ Срочно! {}",
    "Только сегодня: {}",
    "🔥 Топ предложение: {}"
]

def load_active_groups() -> List[str]:
    """Загружает список активных групп из файла"""
    if not os.path.exists(ACTIVE_GROUPS_FILE):
        return []
    with open(ACTIVE_GROUPS_FILE, 'r', encoding='utf-8') as f:
        groups = [line.strip() for line in f if line.strip()]
    return groups

def save_active_groups(groups: List[str]):
    """Сохраняет список активных групп (уникальные)"""
    # Читаем существующие
    existing = []
    if os.path.exists(ACTIVE_GROUPS_FILE):
        with open(ACTIVE_GROUPS_FILE, 'r', encoding='utf-8') as f:
            existing = [line.strip() for line in f if line.strip()]
    # Объединяем и убираем дубли
    all_groups = list(set(existing + groups))
    with open(ACTIVE_GROUPS_FILE, 'w', encoding='utf-8') as f:
        for g in all_groups:
            f.write(f"{g}\n")
    print(f"✅ Сохранено активных групп: {len(all_groups)} в {ACTIVE_GROUPS_FILE}")

def load_message() -> str:
    if not os.path.exists(MESSAGE_FILE):
        print(f"❌ Файл {MESSAGE_FILE} не найден!")
        return None
    with open(MESSAGE_FILE, 'r', encoding='utf-8') as f:
        message = f.read()
    return message

def generate_variation(base_message: str) -> str:
    """Генерирует вариацию сообщения"""
    template = random.choice(TEXT_VARIATIONS)
    msg = template.format(base_message)
    if random.random() < 0.7:
        num_emojis = random.randint(1, 3)
        emoji_suffix = " " + " ".join(random.choices(EMOJIS, k=num_emojis))
        msg += emoji_suffix
    return msg

def parse_entity(raw_id: str) -> Union[int, str, None]:
    """Преобразует сырой ID в число (если числовой) или оставляет как строку (username)"""
    raw = raw_id.strip()
    if not raw:
        return None
    # Если это username (начинается с @ или не похоже на число)
    if raw.startswith('@') or not raw.lstrip('-').isdigit():
        return raw if raw.startswith('@') else f"@{raw}"  # приводим к формату @username
    else:
        return int(raw)

async def join_chat(app: Client, entity: Union[int, str]) -> tuple[bool, object, int]:
    """
    Пытается присоединиться к чату.
    Возвращает (успех, объект чата, количество участников)
    """
    try:
        # Пытаемся вступить
        chat = await app.join_chat(entity)
        # Получаем полную информацию (особенно members_count)
        full_chat = await app.get_chat(chat.id)
        members = getattr(full_chat, 'members_count', 0)
        return True, full_chat, members
    except UserAlreadyParticipant:
        # Уже участник — просто получаем информацию
        chat = await app.get_chat(entity)
        members = getattr(chat, 'members_count', 0)
        return True, chat, members
    except (InviteHashExpired, InviteInvalid, ChatForbidden, ChatAdminRequired, UsernameNotOccupied) as e:
        print(f"   ❌ Не удалось вступить: {e}")
        return False, None, 0
    except FloodWait as e:
        print(f"   ⚠️ Флуд при вступлении, ждём {e.value}с")
        await asyncio.sleep(e.value)
        return False, None, 0
    except Exception as e:
        print(f"   ❌ Ошибка при вступлении: {e}")
        return False, None, 0

async def search_and_add_groups(app: Client):
    """Ищет группы по запросам, вступает, проверяет и добавляет в активные"""
    print(f"\n🔍 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - Начинаю поиск групп...")
    newly_added = []

    for query in SEARCH_QUERIES:
        print(f"   Поиск по запросу: {query}")
        try:
            async for dialog in app.search_global(query, limit=50):
                # Из search_global получаем dialog.chat — это объект чата, но не всегда полный
                chat = dialog.chat
                # Нас интересуют только группы/супергруппы
                if chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
                    continue

                # Определяем entity для вступления: username или ID
                if chat.username:
                    entity = f"@{chat.username}"
                else:
                    entity = chat.id

                print(f"      Найдена: {chat.title} (entity: {entity})")

                # Пытаемся вступить/проверить
                success, full_chat, members = await join_chat(app, entity)
                if not success:
                    continue

                # Проверяем количество участников
                if members < MIN_MEMBERS:
                    print(f"         ⏩ Участников {members} < {MIN_MEMBERS}, пропускаем")
                    continue

                # Группа подходит: сохраняем ID (или username, но лучше числовой ID)
                group_id = str(full_chat.id)
                if group_id not in newly_added:
                    newly_added.append(group_id)
                    print(f"         ✅ Добавлена: {full_chat.title} (ID: {group_id}, участников: {members})")

                # Лимит на количество добавляемых за раз
                if len(newly_added) >= MAX_GROUPS_TO_ADD_PER_SEARCH:
                    break

            if len(newly_added) >= MAX_GROUPS_TO_ADD_PER_SEARCH:
                break

            # Задержка между запросами
            await asyncio.sleep(random.uniform(5, 10))

        except FloodWait as e:
            print(f"⚠️ Флуд при поиске, ждём {e.value}с")
            await asyncio.sleep(e.value)
        except Exception as e:
            print(f"❌ Ошибка при поиске: {e}")

    if newly_added:
        save_active_groups(newly_added)
        print(f"✅ Добавлено {len(newly_added)} новых групп в активный список")
    else:
        print("⚠️ Новых групп не найдено")

async def send_to_active_groups(app: Client):
    """Отправляет сообщение во все активные группы"""
    active_groups = load_active_groups()
    # Добавляем также ручные группы из GROUPS_FILE, если есть
    if os.path.exists(GROUPS_FILE):
        with open(GROUPS_FILE, 'r', encoding='utf-8') as f:
            manual = [line.strip() for line in f if line.strip()]
        active_groups = list(set(active_groups + manual))

    if not active_groups:
        print("❌ Нет активных групп для рассылки")
        return

    base_message = load_message()
    if not base_message:
        print("❌ Нет сообщения для отправки")
        return

    print(f"\n🕒 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - Рассылка в {len(active_groups)} группах...")
    # Перемешиваем
    random.shuffle(active_groups)

    for raw_id in active_groups:
        entity = parse_entity(raw_id)
        if entity is None:
            print(f"❌ Некорректный ID: {raw_id}, пропускаем")
            continue

        # Генерируем вариацию
        message = generate_variation(base_message)

        try:
            # Небольшая случайная задержка перед отправкой
            await asyncio.sleep(random.uniform(3, 8))

            await app.send_message(entity, message)
            print(f"✅ Отправлено в {raw_id}")

        except ChatWriteForbidden:
            print(f"❌ Нет прав на отправку в {raw_id}, удаляем из активных")
            # Удаляем из активного списка
            new_list = [g for g in active_groups if g != raw_id]
            save_active_groups(new_list)
        except (PeerIdInvalid, ChatIdInvalid, ChannelInvalid, UsernameNotOccupied) as e:
            print(f"❌ Чат недоступен {raw_id}: {e}, удаляем из активных")
            new_list = [g for g in active_groups if g != raw_id]
            save_active_groups(new_list)
        except FloodWait as e:
            print(f"⚠️ Флуд-контроль: ждём {e.value}с")
            await asyncio.sleep(e.value)
            # После ожидания можно повторить для этой группы? Пока пропускаем.
        except RPCError as e:
            print(f"❌ Ошибка отправки в {raw_id}: {e}")
        except Exception as e:
            print(f"❌ Неизвестная ошибка для {raw_id}: {e}")

        # Базовая задержка между группами
        await asyncio.sleep(random.uniform(5, 15))

    print("✅ Рассылка завершена")

async def main():
    print("🤖 Умный юзербот (ИИ-режим) запускается на Railway...")
    print(f"📊 Интервал рассылки: {POSTS_PER_HOUR} сообщений/час (каждые {INTERVAL_SECONDS} секунд)")
    print(f"🔍 Поиск новых групп каждые {SEARCH_INTERVAL_HOURS} часов")

    if not all([API_ID, API_HASH, PHONE_NUMBER]):
        print("❌ Ошибка: не заданы API_ID, API_HASH или PHONE_NUMBER")
        return

    app = Client(
        name=SESSION_NAME,
        api_id=API_ID,
        api_hash=API_HASH,
        phone_number=PHONE_NUMBER,
        workdir="./"
    )

    await app.start()
    print("✅ Авторизация успешна")

    loop_counter = 0
    cycles_before_search = max(1, int(SEARCH_INTERVAL_HOURS * 3600 / INTERVAL_SECONDS))

    while True:
        try:
            # 1. Выполняем рассылку по активным группам
            await send_to_active_groups(app)

            loop_counter += 1

            # 2. Периодический поиск новых групп
            if loop_counter % cycles_before_search == 0:
                await search_and_add_groups(app)

            print(f"⏳ Следующая отправка через {INTERVAL_SECONDS} секунд...")
            await asyncio.sleep(INTERVAL_SECONDS)

        except KeyboardInterrupt:
            print("\n🛑 Остановка по команде пользователя")
            break
        except Exception as e:
            print(f"❌ Критическая ошибка: {e}")
            print("⏳ Перезапуск через 60 секунд...")
            await asyncio.sleep(60)

    await app.stop()

if __name__ == "__main__":
    asyncio.run(main())

