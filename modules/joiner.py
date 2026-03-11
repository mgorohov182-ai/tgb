import asyncio
import random
from pyrogram.errors import (
    UserAlreadyParticipant, InviteHashInvalid, 
    UsernameNotOccupied, PeerIdInvalid, ChatWriteForbidden
)

from core.logger import setup_logger
from config import Config

logger = setup_logger()

class GroupJoiner:
    """Вступление в группы и проверка участников"""
    
    def __init__(self, client):
        self.client = client
        self.active_groups = {}
        self.blacklist = set()
        
    async def join_group(self, group_identifier):
        """Вступление в группу по ID, username или invite link"""
        try:
            # Пробуем разные форматы
            if isinstance(group_identifier, str):
                if group_identifier.startswith('https://t.me/+') or group_identifier.startswith('t.me/+'):
                    # Приватная ссылка-приглашение
                    await self.client.join_chat(group_identifier)
                elif group_identifier.startswith('@'):
                    # Username
                    await self.client.join_chat(group_identifier)
                else:
                    # Пробуем как ID
                    try:
                        chat_id = int(group_identifier)
                        await self.client.join_chat(chat_id)
                    except ValueError:
                        # Возможно, просто username без @
                        await self.client.join_chat(f"@{group_identifier}")
            else:
                # ID как число
                await self.client.join_chat(group_identifier)
                
            logger.info(f"✅ Вступил в группу: {group_identifier}")
            return True
            
        except UserAlreadyParticipant:
            logger.info(f"👤 Уже участник: {group_identifier}")
            return True
        except (InviteHashInvalid, UsernameNotOccupied, PeerIdInvalid) as e:
            logger.warning(f"❌ Не удалось вступить в {group_identifier}: недействительная ссылка/ID")
            return False
        except Exception as e:
            logger.error(f"❌ Ошибка при вступлении в {group_identifier}: {e}")
            return False
    
    async def check_group(self, chat_id):
        """Проверка группы (участники, права)"""
        try:
            chat = await self.client.get_chat(chat_id)
            
            # Проверяем количество участников
            members = getattr(chat, 'members_count', 0)
            if members < Config.MIN_MEMBERS:
                logger.info(f"⏩ Группа {chat.title}: {members} < {Config.MIN_MEMBERS} участников")
                return None
            
            # Проверяем права на отправку
            try:
                await self.client.send_message(chat_id, ".", disable_notification=True)
                # Если дошли сюда - есть права
                return {
                    "id": str(chat.id),
                    "title": chat.title,
                    "username": chat.username,
                    "members": members,
                    "active": True,
                    "last_check": None
                }
            except ChatWriteForbidden:
                logger.warning(f"❌ Нет прав на отправку в {chat.title}")
                return None
                
        except Exception as e:
            logger.debug(f"Ошибка проверки группы {chat_id}: {e}")
            return None
    
    async def process_found_groups(self, groups):
        """Обработка найденных групп (вступление + проверка)"""
        valid_groups = []
        
        for group in groups:
            # Пропускаем заблокированные
            if group.get("id") in self.blacklist:
                continue
                
            # Вступаем
            joined = await self.join_group(group.get("id") or group.get("username"))
            if not joined:
                self.blacklist.add(group.get("id"))
                continue
            
            # Небольшая пауза после вступления
            await asyncio.sleep(random.uniform(5, 10))
            
            # Проверяем
            checked = await self.check_group(group.get("id"))
            if checked:
                valid_groups.append(checked)
                
            # Пауза между группами
            await asyncio.sleep(random.uniform(10, 20))
        
        return valid_groups