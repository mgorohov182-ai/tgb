#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Nova Super Bot - Enterprise Edition
Автор: AI Developer Team
Версия: 3.0.0 (Professional)
"""

import asyncio
import sys
from datetime import datetime

# Добавляем пути
sys.path.append('.')

from core.logger import setup_logger
from core.client import TelegramClient
from modules.searcher import GroupSearcher
from modules.joiner import GroupJoiner
from modules.poster import SmartPoster
from modules.brain import Brain
from config import Config

logger = setup_logger("NovaSuperBot")

class NovaSuperBot:
    """Главный класс бота"""
    
    def __init__(self):
        logger.info("🚀 Инициализация Nova Super Bot (Enterprise Edition)...")
        logger.info("=" * 60)
        
        # Проверка конфигурации
        errors = Config.validate()
        if errors:
            for err in errors:
                logger.error(f"❌ {err}")
            sys.exit(1)
        
        # Инициализация компонентов
        self.client = TelegramClient()
        self.searcher = None
        self.joiner = None
        self.poster = None
        self.brain = Brain()
        
        logger.info("✅ Конфигурация загружена")
        logger.info(f"📊 Настройки: {Config.POSTS_PER_HOUR} сообщений/час")
        logger.info(f"🔍 Поиск каждые {Config.SEARCH_INTERVAL_HOURS}ч")
        logger.info(f"👥 Минимум участников: {Config.MIN_MEMBERS}")
        logger.info("=" * 60)
    
    async def initialize(self):
        """Инициализация клиента и модулей"""
        if not await self.client.start():
            return False
        
        self.searcher = GroupSearcher(self.client.client)
        self.joiner = GroupJoiner(self.client.client)
        self.poster = SmartPoster(self.client.client)
        
        return True
    
    async def search_phase(self):
        """Фаза поиска новых групп"""
        logger.info("\n🔍 ФАЗА 1: ПОИСК НОВЫХ ГРУПП")
        
        all_found = []
        
        # 1. Поиск в Telegram по хештегам
        queries_file = Config.QUERIES_FILE
        try:
            with open(queries_file, 'r', encoding='utf-8') as f:
                queries = [q.strip() for q in f.readlines() if q.strip()]
        except FileNotFoundError:
            queries = ["#роблокс", "#roblox", "#роблоксскрипты"]
        
        for query in queries[:3]:  # Ограничиваем для теста
            async for group in self.searcher.search_telegram(query, limit=30):
                all_found.append(group)
        
        # 2. Поиск в Google
        for query in Config.GOOGLE_SEARCH_QUERIES[:2]:
            async for group in self.searcher.search_google(query, pages=1):
                all_found.append(group)
        
        logger.info(f"📊 Найдено потенциальных групп: {len(all_found)}")
        return all_found
    
    async def join_phase(self, found_groups):
        """Фаза вступления и проверки"""
        logger.info("\n👥 ФАЗА 2: ВСТУПЛЕНИЕ И ПРОВЕРКА")
        
        valid = await self.joiner.process_found_groups(found_groups)
        
        if valid:
            added = self.brain.add_groups(valid)
            logger.info(f"✅ Добавлено {added} новых активных групп")
        
        return valid
    
    async def post_phase(self):
        """Фаза рассылки"""
        logger.info("\n📨 ФАЗА 3: РАССЫЛКА")
        
        active = self.brain.get_active_groups()
        if not active:
            logger.warning("Нет активных групп для рассылки")
            return
        
        # Фильтруем по решению мозга
        to_send = {}
        for gid, info in active.items():
            if self.brain.should_send_now(gid):
                to_send[gid] = info
        
        if not to_send:
            logger.info("Мозг решил пропустить рассылку в этом цикле")
            return
        
        logger.info(f"🧠 Мозг выбрал {len(to_send)} групп для рассылки")
        
        # Отправляем
        updated = await self.poster.distribute(to_send)
        
        # Обновляем статусы
        for gid, info in updated.items():
            if info.get("active") == False:
                self.brain.mark_failed(gid, "deactivated")
            elif info.get("last_success"):
                self.brain.mark_success(gid)
    
    async def run(self):
        """Основной цикл работы"""
        logger.info("🤖 Запуск основного цикла...")
        
        if not await self.initialize():
            return
        
        cycle = 0
        
        try:
            while True:
                cycle += 1
                logger.info(f"\n{'='*60}")
                logger.info(f"🔄 ЦИКЛ #{cycle} | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                logger.info(f"{'='*60}")
                
                # Фаза поиска (если пора)
                if self.brain.should_search():
                    found = await self.search_phase()
                    if found:
                        await self.join_phase(found)
                    self.brain.stats["last_search"] = datetime.now().isoformat()
                
                # Фаза рассылки
                await self.post_phase()
                
                # Интервал между циклами
                interval = 3600 // Config.POSTS_PER_HOUR
                logger.info(f"\n⏳ Следующий цикл через {interval} секунд...")
                await asyncio.sleep(interval)
                
        except KeyboardInterrupt:
            logger.info("\n🛑 Бот остановлен пользователем")
        except Exception as e:
            logger.exception(f"💥 Критическая ошибка: {e}")
        finally:
            await self.client.stop()
            logger.info("👋 Бот завершил работу")

if __name__ == "__main__":
    bot = NovaSuperBot()
    asyncio.run(bot.run())