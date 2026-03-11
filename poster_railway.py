import asyncio
import os
from datetime import datetime
from pyrogram import Client
from pyrogram.errors import FloodWait, RPCError, PeerIdInvalid, ChatWriteForbidden, ChatIdInvalid
import time

# ===== НАСТРОЙКИ =====
API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH", "")
PHONE_NUMBER = os.environ.get("PHONE_NUMBER", "")
GROUPS_FILE = "groups.txt"
MESSAGE_FILE = "message.txt"
POSTS_PER_HOUR = int(os.environ.get("POSTS_PER_HOUR", 3))  # по умолчанию 3 в час
SESSION_NAME = "my_account"
# =====================

INTERVAL_SECONDS = 3600 // POSTS_PER_HOUR

def load_groups():
    """Загружает список ID групп из файла, удаляет пустые строки и пробелы"""
    if not os.path.exists(GROUPS_FILE):
        print(f"❌ Файл {GROUPS_FILE} не найден!")
        return []
    with open(GROUPS_FILE, 'r', encoding='utf-8') as f:
        groups = [line.strip() for line in f if line.strip()]
    print(f"✅ Загружено групп: {len(groups)}")
    return groups

def load_message():
    if not os.path.exists(MESSAGE_FILE):
        print(f"❌ Файл {MESSAGE_FILE} не найден!")
        return None
    with open(MESSAGE_FILE, 'r', encoding='utf-8') as f:
        message = f.read()
    print(f"✅ Сообщение загружено ({len(message)} символов)")
    return message

def normalize_chat_id(raw_id):
    """
    Преобразует входной ID в список возможных корректных ID для Pyrogram.
    raw_id может быть строкой или числом.
    Возвращает список целых чисел (кандидатов).
    """
    candidates = []
    # Убираем лишние пробелы и преобразуем в строку
    raw = str(raw_id).strip()
    # Пытаемся интерпретировать как целое число
    try:
        int_id = int(raw)
        candidates.append(int_id)
        # Если это отрицательное число без префикса -100, добавим вариант с -100
        if int_id < 0 and str(int_id).startswith('-') and not str(int_id).startswith('-100'):
            # Возможно, это старая группа, нужно добавить -100
            candidates.append(int(f"-100{abs(int_id)}"))
        # Если начинается с -100, попробуем убрать -100 (для старых групп)
        if str(int_id).startswith('-100'):
            # Убираем -100, оставляем остаток
            rest = str(int_id)[4:]  # после -100
            if rest.lstrip('-').isdigit():
                candidates.append(int(rest))
    except ValueError:
        # Если не число, может быть строкой вида "t.me/joinchat/..." – не поддерживается
        pass
    # Убираем дубликаты, сохраняя порядок
    seen = set()
    unique_candidates = []
    for c in candidates:
        if c not in seen:
            seen.add(c)
            unique_candidates.append(c)
    return unique_candidates

async def send_to_all_groups(app):
    groups = load_groups()
    message = load_message()
    if not groups or not message:
        print("❌ Нет групп или сообщения для отправки")
        return

    print(f"\n🕒 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - Начинаю рассылку...")

    for raw_id in groups:
        # Пробуем разные варианты ID
        candidates = normalize_chat_id(raw_id)
        if not candidates:
            print(f"❌ Не удалось распознать ID: {raw_id} — пропускаем")
            continue

        sent = False
        for chat_id in candidates:
            try:
                # Сначала проверим существование чата и права
                chat = await app.get_chat(chat_id)
                # Если чат получен, отправляем сообщение
                await app.send_message(chat_id, message)
                print(f"✅ Отправлено в {chat_id} (из исходного '{raw_id}')")
                sent = True
                break  # удалось отправить, выходим из цикла кандидатов
            except PeerIdInvalid:
                # Неверный ID — пробуем следующий кандидат
                continue
            except ChatIdInvalid:
                continue
            except ChatWriteForbidden:
                print(f"❌ Нет прав на отправку в {chat_id} (исходный '{raw_id}') — пропускаем группу")
                # Можно выйти из цикла кандидатов, т.к. права не зависят от формата ID
                break
            except FloodWait as e:
                print(f"⚠️ Флуд-контроль: нужно подождать {e.value} секунд")
                await asyncio.sleep(e.value)
                # После ожидания можно повторить попытку с тем же кандидатом? Но чтобы не усложнять, просто выйдем из цикла и продолжим следующую группу позже.
                # Так как мы внутри цикла по группам, лучше подождать и затем повторить эту же группу? Но тогда может быть бесконечно.
                # Просто ждём и продолжаем текущую группу? Сейчас мы просто ждём и затем пытаемся следующего кандидата.
                # На самом деле после ожидания можно повторить отправку в тот же чат, но для простоты пропустим эту группу на этом цикле.
                break
            except RPCError as e:
                print(f"❌ Ошибка RPC при отправке в {chat_id}: {e}")
                # Если ошибка, возможно, стоит попробовать другой кандидат
                continue
            except Exception as e:
                print(f"❌ Неизвестная ошибка для {chat_id}: {e}")
                continue

        if not sent:
            print(f"❌ Не удалось отправить сообщение в группу с исходным ID '{raw_id}' — ни один кандидат не подошёл")

        # Небольшая задержка между группами, чтобы не вызвать флуд
        await asyncio.sleep(5)

    print("✅ Рассылка завершена")

async def main():
    print("🤖 Юзербот запускается на Railway...")
    if not all([API_ID, API_HASH, PHONE_NUMBER]):
        print("❌ Ошибка: не заданы API_ID, API_HASH или PHONE_NUMBER в переменных окружения")
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

    while True:
        try:
            await send_to_all_groups(app)
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
