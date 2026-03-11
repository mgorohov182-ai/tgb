import asyncio
import random
import time
from datetime import datetime
from pyrogram.errors import FloodWait, ChatWriteForbidden, PeerIdInvalid

from core.logger import setup_logger
from config import Config

logger = setup_logger()

class SmartPoster:
    """Умная рассылка с вариациями и защитой"""
    
    def __init__(self, client):
        self.client = client
        self.base_message = self._load_message()
        self.emojis = ["🔥", "🚀", "💎", "⚡️", "🎯", "💯", "👑", "⭐️", "✨", "🎮"]
        self.templates = [
            "{base}",
            "🔥 {base}",
            "{base} 🔥",
            "⚡️ СРОЧНО: {base}",
            "🚀 {base} 🚀",
            "ВНИМАНИЕ! {base}",
            "{base}\n\n👇 Присоединяйся! 👇",
            "💎 ЭКСКЛЮЗИВ: {base}",
            "{base} 🎁 Бонусы всем!",
            "⚡️ Только сегодня: {base}"
        ]
        
    def _load_message(self):
        """Загрузка базового сообщения"""
        try:
            with open(Config.MESSAGE_FILE, 'r', encoding='utf-8') as f:
                return f.read().strip()
        except Exception as e:
            logger.error(f"❌ Ошибка загрузки сообщения: {e}")
            return None
    
    def generate_variation(self):
        """Генерация вариации сообщения"""
        if not self.base_message:
            return None
            
        # Выбираем шаблон
        template = random.choice(self.templates)
        message = template.format(base=self.base_message)
        
        # Добавляем эмодзи
        if random.random() < 0.8:
            num = random.randint(1, 4)
            message += " " + " ".join(random.choices(self.emojis, k=num))
        
        # Иногда добавляем хештеги
        if random.random() < 0.3:
            hashtags = [" #roblox", " #скрипты", " #роблокс"]
            message += random.choice(hashtags)
            
        return message
    
    async def send_with_protection(self, chat_id, message):
        """Отправка с защитой и умными задержками"""
        
        # Рандомная задержка перед отправкой (3-10 секунд)
        await asyncio.sleep(random.uniform(3, 10))
        
        try:
            sent = await self.client.send_message(chat_id, message)
            logger.info(f"✅ Отправлено в {chat_id}")
            
            # Иногда "лайкаем" своё сообщение (имитация человека)
            if random.random() < 0.2:
                await asyncio.sleep(random.uniform(1, 3))
                await self.client.send_reaction(chat_id, sent.id, "👍")
                
            return True, None
            
        except FloodWait as e:
            wait = e.value
            logger.warning(f"⚠️ Flood wait {wait}с")
            await asyncio.sleep(wait)
            return False, "flood"
            
        except ChatWriteForbidden:
            logger.warning(f"❌ Нет прав в {chat_id}")
            return False, "no_rights"
            
        except PeerIdInvalid:
            logger.warning(f"❌ Неверный ID: {chat_id}")
            return False, "invalid_id"
            
        except Exception as e:
            logger.error(f"❌ Ошибка отправки в {chat_id}: {e}")
            return False, "unknown"
    
    async def distribute(self, groups):
        """Распределение сообщений по группам"""
        if not groups:
            logger.warning("Нет групп для рассылки")
            return
            
        # Перемешиваем группы
        shuffled = list(groups.items())
        random.shuffle(shuffled)
        
        success = 0
        failed = 0
        
        for chat_id, info in shuffled:
            if not info.get("active", True):
                continue
                
            message = self.generate_variation()
            if not message:
                continue
                
            ok, reason = await self.send_with_protection(chat_id, message)
            
            if ok:
                success += 1
                info["last_success"] = datetime.now().isoformat()
                info["fail_count"] = 0
            else:
                failed += 1
                info["fail_count"] = info.get("fail_count", 0) + 1
                
                # Если слишком много ошибок - деактивируем
                if info["fail_count"] >= 3:
                    info["active"] = False
                    logger.warning(f"⚠️ Группа {chat_id} деактивирована")
            
            # Базовая задержка между группами
            await asyncio.sleep(random.uniform(15, 30))
        
        logger.info(f"📊 Рассылка завершена: ✅ {success} успешно, ❌ {failed} ошибок")
        return groups