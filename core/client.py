from pyrogram import Client
from pyrogram.errors import RPCError, FloodWait
import asyncio
from .logger import setup_logger
from config import Config

logger = setup_logger()

class TelegramClient:
    """Управление клиентом Telegram"""
    
    def __init__(self):
        self.client = None
        self._lock = asyncio.Lock()
        
    async def start(self):
        """Запуск клиента"""
        async with self._lock:
            if self.client and self.client.is_connected:
                return True
                
            try:
                client_kwargs = {
                    "name": Config.SESSION_NAME,
                    "api_id": Config.API_ID,
                    "api_hash": Config.API_HASH,
                    "phone_number": Config.PHONE_NUMBER,
                    "workdir": "./"
                }
                
                if Config.USE_PROXY and Config.PROXY["hostname"]:
                    client_kwargs["proxy"] = Config.PROXY
                
                self.client = Client(**client_kwargs)
                await self.client.start()
                logger.info("✅ Клиент успешно запущен")
                return True
                
            except Exception as e:
                logger.error(f"❌ Ошибка запуска клиента: {e}")
                return False
    
    async def stop(self):
        """Остановка клиента"""
        async with self._lock:
            if self.client:
                await self.client.stop()
                logger.info("Клиент остановлен")
    
    async def safe_execute(self, func, *args, **kwargs):
        """Безопасное выполнение с обработкой ошибок"""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                return await func(*args, **kwargs)
            except FloodWait as e:
                wait = e.value
                logger.warning(f"⚠️ Flood wait: {wait} секунд")
                await asyncio.sleep(wait)
            except RPCError as e:
                if attempt == max_retries - 1:
                    logger.error(f"❌ RPC ошибка после {max_retries} попыток: {e}")
                    raise
                await asyncio.sleep(2 ** attempt)
            except Exception as e:
                logger.error(f"❌ Неизвестная ошибка: {e}")
                raise
        return None