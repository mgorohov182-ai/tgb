import asyncio
import os
import random
import re
from datetime import datetime
from typing import List, Dict, Any, Set

from pyrogram import Client
from pyrogram.errors import FloodWait, RPCError, PeerIdInvalid, ChatWriteForbidden, ChatIdInvalid, ChannelInvalid, UsernameNotOccupied, UserAlreadyParticipant, InviteHashExpired, InviteRequestSent
from pyrogram.enums import ChatType
import time

# ===== НАСТРОЙКИ =====
API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH", "")
PHONE_NUMBER = os.environ.get("PHONE_NUMBER", "")
GROUPS_FILE = "groups.txt"              # Ручной список групп (вы уже участник)
AUTO_GROUPS_FILE = "groups_auto.txt"     # Автоматически найденные и добавленные группы
MESSAGE_FILE = "message.txt"
POSTS_PER_HOUR = int(os.environ.get("POSTS_PER_HOUR", 5))  # 5 сообщений в час
SESSION_NAME = "my_account"

# Настройки авто-поиска
SEARCH_QUERIES = [
    "#роблокс", "#роблоксскрипты", "#роблоксчиты", "#роблоксобщение",
    "#roblox", "#robloxscripts", "#robloxhacks", "#robloxexploits",
    "roblox scripts", "roblox hack", "роблокс скрипты"
]
MIN_MEMBERS = 100          # Минимальное количество участников для добавления
MAX_GROUPS_TO_ADD = 10     # Сколько новых групп добавлять за один поиск
SEARCH_INTERVAL_HOURS = 6  # Как часто искать новые группы (в часах)
# =====================

INTERVAL_SECONDS = 3600 // POSTS_PER_HOUR  # интервал между отправками в секундах

# Эмодзи и вариации текста для обхода антиспама
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

def load_groups(file_path: str) -> Set[str]:
    """Загружает список ID групп из файла в множество (для быстрой проверки)"""
    if not os.path.exists(file_path):
        return set()
    with open(file_path, 'r', encoding='utf-8') as f:
        groups = {line.strip() for line in f if line.strip()}
    return groups

def save_groups(groups: Set[str], file_path: str):
    """Сохраняет множество ID групп в файл"""
    with open(file_path, 'w', encoding='utf-8') as f:
        for g in sorted(groups):
            f.write(f"{g}\n")

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
    message = template.format(base_message)
    if random.random() < 0.7:
        num_emojis = random.randint(1, 3)
        emoji_suffix = " " + " ".join(random.choices(EMOJIS, k=num_emojis))
        message += emoji_suffix
    return message

def normalize_chat_id(raw_id) -> List[int]:
    """Преобразует ID в список кандидатов (для отправки)"""
    candidates = []
    raw = str(raw_id).strip()
    try:
        int_id = int(raw)
        candidates.append(int_id)
        if int_id < 0 and not raw.startswith('-100'):
            candidates.append(int(f"-100{abs(int_id)}"))
        if raw.startswith('-100'):
            rest = raw[4:]
            if rest.lstrip('-').isdigit():
                candidates.append(int(rest))
    except ValueError:
        # Если это username, оставляем как есть (строка)
        if raw.startswith('@') or not raw.startswith('-'):
            candidates.append(raw)
    return candidates

async def search_and_add_groups(app: Client):
    """
    Ищет группы по хештегам, вступает в них и добавляет в auto_groups.txt, если >= MIN_MEMBERS
    """
    print(f"\n🔍 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - Начинаю поиск групп...")
    
    # Загружаем уже имеющиеся авто-группы, чтобы не дублировать
    existing_auto = load_groups(AUTO_GROUPS_FILE)
    # Также можно учесть ручные группы, чтобы не добавлять их повторно, но ручные могут быть другими ID
    # Но для простоты просто проверяем auto файл.
    
    new_groups = set()
    
    for query in SEARCH_QUERIES:
        try:
            print(f"   Поиск по запросу: {query}")
            # Глобальный поиск
            async for dialog in app.search_global(query, limit=50):
                chat = dialog.chat
                # Нас интересуют только группы и супергруппы
                if chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
                    continue
                
                # Проверяем, не добавлена ли уже эта группа
                if str(chat.id) in existing_auto:
                    continue
                
                # Пытаемся вступить
                try:
                    await app.join_chat(chat.id)
                    print(f"      ➕ Вступил в группу {chat.title}")
                except UserAlreadyParticipant:
                    print(f"      ℹ️ Уже участник {chat.title}")
                except (InviteHashExpired, InviteRequestSent) as e:
                    print(f"      ⚠️ Не удалось вступить (требуется подтверждение или ссылка недействительна): {e}")
                    continue
                except Exception as e:
                    print(f"      ⚠️ Ошибка вступления в {chat.title}: {e}")
                    continue
                
                # Получаем актуальную информацию о группе (чтобы узнать количество участников)
                try:
                    full_chat = await app.get_chat(chat.id)
                    members = full_chat.members_count if full_chat.members_count else 0
                except Exception as e:
                    print(f"      ⚠️ Не удалось получить информацию о {chat.title}: {e}")
                    members = 0
                
                if members >= MIN_MEMBERS:
                    new_groups.add(str(chat.id))
                    print(f"      ✅ Добавлена группа {chat.title} (участников: {members})")
                else:
                    print(f"      ⏩ Группа {chat.title} имеет {members} участников (<{MIN_MEMBERS}) — пропускаем")
                    # Можно выйти из группы, чтобы не засорять аккаунт
                    try:
                        await app.leave_chat(chat.id)
                        print(f"      👋 Покинул группу {chat.title}")
                    except:
                        pass
                
                # Лимит на количество добавляемых групп за один поиск
                if len(new_groups) >= MAX_GROUPS_TO_ADD:
                    break
                
                # Небольшая задержка между обработкой групп
                await asyncio.sleep(random.uniform(2, 5))
                
        except FloodWait as e:
            print(f"⚠️ Флуд при поиске, ждём {e.value}с")
            await asyncio.sleep(e.value)
        except Exception as e:
            print(f"❌ Ошибка при поиске: {e}")
        
        # Задержка между запросами
        await asyncio.sleep(random.uniform(5, 10))
    
    # Сохраняем новые группы
    if new_groups:
        existing_auto.update(new_groups)
        save_groups(existing_auto, AUTO_GROUPS_FILE)
        print(f"✅ Добавлено {len(new_groups)} новых групп в {AUTO_GROUPS_FILE}")
    else:
        print("⚠️ Новых групп не найдено")

async def send_to_all_groups(app: Client):
    """Отправляет сообщение во все группы (ручные + автоматические)"""
    manual_groups = load_groups(GROUPS_FILE)
    auto_groups = load_groups(AUTO_GROUPS_FILE) if os.path.exists(AUTO_GROUPS_FILE) else set()
    
    all_groups = manual_groups.union(auto_groups)
    
    if not all_groups:
        print("❌ Нет групп для отправки")
        return
    
    base_message = load_message()
    if not base_message:
        print("❌ Нет сообщения для отправки")
        return
    
    print(f"\n🕒 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - Начинаю рассылку в {len(all_groups)} групп...")
    
    # Преобразуем в список и перемешиваем
    groups_list = list(all_groups)
    random.shuffle(groups_list)
    
    for raw_id in groups_list:
        candidates = normalize_chat_id(raw_id)
        if not candidates:
            print(f"❌ Не удалось распознать ID: {raw_id} — пропускаем")
            continue
        
        message = generate_variation(base_message)
        sent = False
        last_error = None
        
        for chat_id in candidates:
            try:
                # Рандомная задержка перед отправкой
                await asyncio.sleep(random.uniform(3, 8))
                await app.send_message(chat_id, message)
                print(f"✅ Отправлено в {chat_id} (из '{raw_id}')")
                sent = True
                break
            except (PeerIdInvalid, ChatIdInvalid, ChannelInvalid, UsernameNotOccupied) as e:
                last_error = e
                continue
            except ChatWriteForbidden as e:
                print(f"❌ Нет прав на отправку в {chat_id} (исходный '{raw_id}') — пропускаем группу")
                last_error = e
                break
            except FloodWait as e:
                print(f"⚠️ Флуд-контроль: ждём {e.value}с")
                await asyncio.sleep(e.value)
                continue
            except RPCError as e:
                last_error = e
                continue
            except Exception as e:
                print(f"❌ Неизвестная ошибка для {chat_id}: {e}")
                last_error = e
                continue
        
        if not sent:
            error_info = f": {last_error}" if last_error else ""
            print(f"❌ Не удалось отправить в группу '{raw_id}'{error_info}")
        
        # Задержка между группами
        await asyncio.sleep(random.uniform(5, 15))
    
    print("✅ Рассылка завершена")

async def main():
    print("🤖 Умный юзербот запускается на Railway...")
    print(f"📊 Интервал рассылки: {POSTS_PER_HOUR} сообщений/час (каждые {INTERVAL_SECONDS} сек)")
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
    
    # Создаём файлы, если их нет
    if not os.path.exists(GROUPS_FILE):
        with open(GROUPS_FILE, 'w') as f:
            pass
    if not os.path.exists(AUTO_GROUPS_FILE):
        with open(AUTO_GROUPS_FILE, 'w') as f:
            pass
    
    loop_counter = 0
    cycles_before_search = int(SEARCH_INTERVAL_HOURS * 3600 / INTERVAL_SECONDS)
    
    while True:
        try:
            # Основная рассылка
            await send_to_all_groups(app)
            
            loop_counter += 1
            
            # Периодический поиск новых групп
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
