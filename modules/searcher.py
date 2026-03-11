import asyncio
import aiohttp
from bs4 import BeautifulSoup
import random
from fake_useragent import UserAgent
from pyrogram.enums import ChatType
from pyrogram.errors import FloodWait
import json

from core.logger import setup_logger
from config import Config

logger = setup_logger()

class GroupSearcher:
    """Поиск групп в Telegram и интернете"""
    
    def __init__(self, client):
        self.client = client
        self.ua = UserAgent()
        self.found_groups = []
        
    async def search_telegram(self, query, limit=50):
        """Поиск внутри Telegram через глобальный поиск"""
        try:
            logger.info(f"🔍 Поиск в Telegram: '{query}'")
            async for dialog in self.client.search_global(query, limit=limit):
                if dialog.chat.type in (ChatType.GROUP, ChatType.SUPERGROUP):
                    yield {
                        "id": str(dialog.chat.id),
                        "title": dialog.chat.title,
                        "username": dialog.chat.username,
                        "type": "telegram_search",
                        "source": query
                    }
                await asyncio.sleep(random.uniform(1, 3))
                
        except FloodWait as e:
            logger.warning(f"⚠️ Flood в Telegram поиске: ждём {e.value}с")
            await asyncio.sleep(e.value)
        except Exception as e:
            logger.error(f"❌ Ошибка Telegram поиска: {e}")
    
    async def search_google(self, query, pages=3):
        """Поиск ссылок на Telegram группы через Google"""
        if not Config.GOOGLE_SEARCH_ENABLED:
            return
            
        logger.info(f"🔍 Поиск в Google: '{query}'")
        
        headers = {"User-Agent": self.ua.random}
        
        async with aiohttp.ClientSession() as session:
            for page in range(pages):
                try:
                    url = f"https://www.google.com/search?q={query}&start={page*10}"
                    async with session.get(url, headers=headers) as response:
                        if response.status != 200:
                            continue
                            
                        html = await response.text()
                        soup = BeautifulSoup(html, 'html.parser')
                        
                        # Ищем ссылки на Telegram
                        for link in soup.find_all('a'):
                            href = link.get('href', '')
                            if 't.me/' in href or 'telegram.me/' in href:
                                # Извлекаем username или invite
                                parts = href.split('t.me/')
                                if len(parts) > 1:
                                    username = parts[1].split('/')[0].split('?')[0]
                                    if username and not username.startswith('joinchat'):
                                        yield {
                                            "id": username,
                                            "type": "google_search",
                                            "source": query,
                                            "url": href
                                        }
                        
                        await asyncio.sleep(random.uniform(5, 10))
                        
                except Exception as e:
                    logger.error(f"❌ Ошибка Google поиска: {e}")
    
    async def search_catalogs(self):
        """Поиск в каталогах Telegram групп"""
        catalogs = [
            "https://tlgrm.ru/channels",
            "https://tgstat.ru/channels"
        ]
        
        for catalog in catalogs:
            try:
                logger.info(f"🔍 Поиск в каталоге: {catalog}")
                # Здесь можно добавить парсинг каталогов
                # (реализация зависит от структуры конкретных сайтов)
                await asyncio.sleep(random.uniform(2, 5))
            except Exception as e:
                logger.error(f"❌ Ошибка парсинга каталога: {e}")