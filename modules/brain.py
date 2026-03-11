import json
import os
from datetime import datetime, timedelta
import random

from core.logger import setup_logger
from config import Config

logger = setup_logger()

class Brain:
    """Мозг бота - принимает решения"""
    
    def __init__(self):
        self.active_groups = {}
        self.blacklist = set()
        self.stats = {
            "total_sent": 0,
            "total_joined": 0,
            "last_search": None,
            "errors": {}
        }
        self._load_data()
        
    def _load_data(self):
        """Загрузка данных из файлов"""
        # Активные группы
        if os.path.exists(Config.ACTIVE_GROUPS_FILE):
            try:
                with open(Config.ACTIVE_GROUPS_FILE, 'r', encoding='utf-8') as f:
                    self.active_groups = json.load(f)
                logger.info(f"📂 Загружено {len(self.active_groups)} активных групп")
            except Exception as e:
                logger.error(f"Ошибка загрузки активных групп: {e}")
        
        # Черный список
        if os.path.exists(Config.BLACKLIST_FILE):
            try:
                with open(Config.BLACKLIST_FILE, 'r', encoding='utf-8') as f:
                    self.blacklist = set(json.load(f))
                logger.info(f"📂 Загружено {len(self.blacklist)} групп в черном списке")
            except Exception as e:
                logger.error(f"Ошибка загрузки черного списка: {e}")
        
        # Статистика
        if os.path.exists(Config.STATS_FILE):
            try:
                with open(Config.STATS_FILE, 'r', encoding='utf-8') as f:
                    self.stats.update(json.load(f))
            except Exception as e:
                logger.error(f"Ошибка загрузки статистики: {e}")
    
    def _save_data(self):
        """Сохранение данных"""
        # Активные группы
        with open(Config.ACTIVE_GROUPS_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.active_groups, f, ensure_ascii=False, indent=2)
        
        # Черный список
        with open(Config.BLACKLIST_FILE, 'w', encoding='utf-8') as f:
            json.dump(list(self.blacklist), f, ensure_ascii=False, indent=2)
        
        # Статистика
        with open(Config.STATS_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.stats, f, ensure_ascii=False, indent=2)
    
    def should_search(self):
        """Проверка, пора ли искать новые группы"""
        if not self.stats["last_search"]:
            return True
            
        last = datetime.fromisoformat(self.stats["last_search"])
        elapsed = (datetime.now() - last).total_seconds()
        return elapsed >= Config.SEARCH_INTERVAL_HOURS * 3600
    
    def add_groups(self, new_groups):
        """Добавление новых групп с приоритетами"""
        added = 0
        for group in new_groups:
            gid = group["id"]
            
            # Проверяем, не в черном ли списке
            if gid in self.blacklist:
                continue
                
            # Проверяем, не слишком ли много групп
            if len(self.active_groups) >= Config.MAX_GROUPS:
                # Удаляем самую старую неактивную
                inactive = [k for k, v in self.active_groups.items() 
                           if not v.get("active", True)]
                if inactive:
                    oldest = min(inactive, 
                               key=lambda x: self.active_groups[x].get("added", ""))
                    del self.active_groups[oldest]
                else:
                    break
            
            # Добавляем с метаданными
            self.active_groups[gid] = {
                "title": group.get("title", "Unknown"),
                "members": group.get("members", 0),
                "added": datetime.now().isoformat(),
                "last_success": None,
                "fail_count": 0,
                "active": True,
                "source": group.get("source", "unknown")
            }
            added += 1
        
        if added:
            logger.info(f"🧠 Мозг: добавлено {added} новых групп")
            self.stats["total_joined"] += added
            self._save_data()
        
        return added
    
    def should_send_now(self, group_id):
        """Интеллектуальное решение - отправлять ли сейчас"""
        group = self.active_groups.get(group_id, {})
        
        # Если группа неактивна - не отправляем
        if not group.get("active", True):
            return False
        
        # Если слишком много ошибок - не отправляем
        if group.get("fail_count", 0) >= 3:
            return False
        
        # Если отправляли недавно - проверяем интервал
        last = group.get("last_success")
        if last:
            last_time = datetime.fromisoformat(last)
            elapsed = (datetime.now() - last_time).total_seconds()
            # Минимальный интервал 30 минут
            if elapsed < 1800:
                return False
        
        # 90% вероятность отправки (чтобы иногда пропускать)
        return random.random() < 0.9
    
    def mark_failed(self, group_id, reason):
        """Отметить ошибку"""
        if group_id in self.active_groups:
            self.active_groups[group_id]["fail_count"] = \
                self.active_groups[group_id].get("fail_count", 0) + 1
            
            # Если слишком много ошибок - в черный список
            if self.active_groups[group_id]["fail_count"] >= 5:
                self.blacklist.add(group_id)
                del self.active_groups[group_id]
                logger.warning(f"🧠 Группа {group_id} отправлена в черный список")
        
        # Обновляем статистику
        self.stats["errors"][reason] = self.stats["errors"].get(reason, 0) + 1
        self._save_data()
    
    def mark_success(self, group_id):
        """Отметить успех"""
        if group_id in self.active_groups:
            self.active_groups[group_id]["last_success"] = datetime.now().isoformat()
            self.active_groups[group_id]["fail_count"] = 0
            self.stats["total_sent"] += 1
            self._save_data()
    
    def get_active_groups(self):
        """Получить активные группы для рассылки"""
        return {k: v for k, v in self.active_groups.items() 
                if v.get("active", True) and k not in self.blacklist}