# modules/inventory_manager.py
"""
Модуль управления инвентори хостов для удалённого аудита.
Поддерживает создание, обновление и фильтрацию инвентори.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from utils.logger import log_info, log_warn, log_fail


@dataclass
class HostEntry:
    """Запись о хосте в инвентори."""
    ip: str
    hostname: Optional[str] = None
    ssh_port: int = 22
    ssh_user: str = "root"
    ssh_key: Optional[str] = None
    ssh_password: Optional[str] = None
    profile: Optional[str] = None
    os: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    vars: Dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        """Конвертация в словарь."""
        data = asdict(self)
        # Удаляем пустые поля для более чистого YAML
        return {k: v for k, v in data.items() if v is not None and v != [] and v != {}}
    
    def matches_filter(
        self,
        *,
        tags: Optional[List[str]] = None,
        os_filter: Optional[str] = None,
        enabled_only: bool = True,
    ) -> bool:
        """Проверяет, соответствует ли хост фильтрам."""
        if enabled_only and not self.enabled:
            return False
        
        if tags:
            if not any(tag in self.tags for tag in tags):
                return False
        
        if os_filter and self.os:
            if os_filter.lower() not in self.os.lower():
                return False
        
        return True


@dataclass
class HostGroup:
    """Группа хостов с общими настройками."""
    name: str
    hosts: List[HostEntry] = field(default_factory=list)
    vars: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Конвертация в словарь."""
        return {
            "vars": self.vars if self.vars else None,
            "hosts": [h.to_dict() for h in self.hosts]
        }
    
    def add_host(self, host: HostEntry) -> None:
        """Добавляет хост в группу."""
        # Проверка на дубликаты
        if not any(h.ip == host.ip for h in self.hosts):
            self.hosts.append(host)
    
    def remove_host(self, ip: str) -> bool:
        """Удаляет хост из группы по IP."""
        initial_len = len(self.hosts)
        self.hosts = [h for h in self.hosts if h.ip != ip]
        return len(self.hosts) < initial_len
    
    def get_host(self, ip: str) -> Optional[HostEntry]:
        """Получает хост по IP."""
        for host in self.hosts:
            if host.ip == ip:
                return host
        return None
    
    def filter_hosts(
        self,
        *,
        tags: Optional[List[str]] = None,
        os_filter: Optional[str] = None,
        enabled_only: bool = True,
    ) -> List[HostEntry]:
        """Фильтрует хосты в группе."""
        return [
            h for h in self.hosts 
            if h.matches_filter(tags=tags, os_filter=os_filter, enabled_only=enabled_only)
        ]


@dataclass
class Inventory:
    """Инвентори хостов."""
    version: str = "1.0"
    updated: str = field(default_factory=lambda: time.strftime("%Y-%m-%d %H:%M:%S"))
    groups: Dict[str, HostGroup] = field(default_factory=dict)
    security: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Конвертация в словарь для сериализации."""
        return {
            "version": self.version,
            "updated": self.updated,
            "security": self.security if self.security else None,
            "groups": {name: group.to_dict() for name, group in self.groups.items()}
        }
    
    def add_group(self, name: str, vars: Optional[Dict[str, Any]] = None) -> HostGroup:
        """Добавляет новую группу."""
        if name not in self.groups:
            self.groups[name] = HostGroup(name=name, vars=vars or {})
        return self.groups[name]
    
    def get_group(self, name: str) -> Optional[HostGroup]:
        """Получает группу по имени."""
        return self.groups.get(name)
    
    def remove_group(self, name: str) -> bool:
        """Удаляет группу."""
        if name in self.groups:
            del self.groups[name]
            return True
        return False
    
    def add_host(
        self,
        host: HostEntry,
        group_name: str = "default",
    ) -> None:
        """Добавляет хост в указанную группу."""
        group = self.add_group(group_name)
        group.add_host(host)
        self.updated = time.strftime("%Y-%m-%d %H:%M:%S")
    
    def remove_host(self, ip: str, group_name: Optional[str] = None) -> bool:
        """Удаляет хост по IP из группы или всех групп."""
        removed = False
        
        if group_name:
            group = self.get_group(group_name)
            if group:
                removed = group.remove_host(ip)
        else:
            # Удаляем из всех групп
            for group in self.groups.values():
                if group.remove_host(ip):
                    removed = True
        
        if removed:
            self.updated = time.strftime("%Y-%m-%d %H:%M:%S")
        
        return removed
    
    def get_host(self, ip: str) -> Optional[tuple[HostEntry, str]]:
        """Находит хост по IP и возвращает его вместе с именем группы."""
        for group_name, group in self.groups.items():
            host = group.get_host(ip)
            if host:
                return host, group_name
        return None
    
    def get_all_hosts(
        self,
        *,
        group: Optional[str] = None,
        tags: Optional[List[str]] = None,
        os_filter: Optional[str] = None,
        enabled_only: bool = True,
    ) -> List[tuple[HostEntry, str]]:
        """
        Получает все хосты с учётом фильтров.
        
        Returns:
            Список кортежей (хост, имя_группы)
        """
        results: List[tuple[HostEntry, str]] = []
        
        groups_to_check = [self.groups[group]] if group and group in self.groups else self.groups.values()
        
        for grp in groups_to_check:
            filtered = grp.filter_hosts(tags=tags, os_filter=os_filter, enabled_only=enabled_only)
            results.extend((host, grp.name) for host in filtered)
        
        return results
    
    def get_host_count(self, enabled_only: bool = True) -> int:
        """Возвращает общее количество хостов."""
        count = 0
        for group in self.groups.values():
            count += len(group.filter_hosts(enabled_only=enabled_only))
        return count
    
    def get_group_names(self) -> List[str]:
        """Возвращает список имён групп."""
        return list(self.groups.keys())


class InventoryManager:
    """Менеджер для работы с инвентори."""
    
    def __init__(self, inventory_path: Optional[Path] = None):
        self.inventory_path = inventory_path
        self.inventory: Optional[Inventory] = None
        
        if inventory_path and inventory_path.exists():
            self.load()
    
    def load(self, path: Optional[Path] = None) -> Inventory:
        """Загружает инвентори из файла."""
        if path:
            self.inventory_path = path
        
        if not self.inventory_path or not self.inventory_path.exists():
            raise FileNotFoundError(f"Файл инвентори не найден: {self.inventory_path}")
        
        try:
            import yaml
        except ImportError:
            log_fail("PyYAML не установлен. Используйте: pip install PyYAML")
            raise
        
        with open(self.inventory_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f) or {}
        
        self.inventory = self._dict_to_inventory(data)
        log_info(f"Инвентори загружен из {self.inventory_path}")
        
        return self.inventory
    
    def save(self, path: Optional[Path] = None) -> None:
        """Сохраняет инвентори в файл."""
        if not self.inventory:
            raise ValueError("Инвентори не инициализирован")
        
        if path:
            self.inventory_path = path
        
        if not self.inventory_path:
            raise ValueError("Не указан путь для сохранения инвентори")
        
        try:
            import yaml
        except ImportError:
            log_fail("PyYAML не установлен. Используйте: pip install PyYAML")
            raise
        
        self.inventory_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Обновляем timestamp
        self.inventory.updated = time.strftime("%Y-%m-%d %H:%M:%S")
        
        data = self.inventory.to_dict()
        
        with open(self.inventory_path, 'w', encoding='utf-8') as f:
            yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
        
        log_info(f"Инвентори сохранён в {self.inventory_path}")
    
    def create_from_scan(
        self,
        scan_results: List[Any],
        *,
        auto_group: bool = False,
        default_group: str = "discovered",
        ssh_user: str = "root",
        ssh_key: Optional[str] = None,
        default_profile: Optional[str] = None,
    ) -> Inventory:
        """
        Создаёт инвентори из результатов сканирования.
        
        Args:
            scan_results: Список ScanResult объектов
            auto_group: Автоматически группировать хосты по подсетям
            default_group: Имя группы по умолчанию
            ssh_user: SSH пользователь по умолчанию
            ssh_key: Путь к SSH ключу по умолчанию
            default_profile: Профиль аудита по умолчанию
        """
        self.inventory = Inventory()
        
        for result in scan_results:
            if not result.is_alive:
                continue
            
            # Определяем группу
            group_name = default_group
            if auto_group:
                # Группируем по /24 подсети
                ip_parts = result.ip.split('.')
                if len(ip_parts) == 4:
                    subnet = '.'.join(ip_parts[:3])
                    group_name = f"subnet_{subnet}_0"
            
            # Создаём host entry
            host = HostEntry(
                ip=result.ip,
                hostname=result.hostname,
                ssh_port=result.ssh_port or 22,
                ssh_user=ssh_user,
                ssh_key=ssh_key,
                profile=default_profile,
                os=result.os_detected,
                tags=[]
            )
            
            # Добавляем теги на основе обнаруженной ОС
            if result.os_detected:
                host.tags.append(result.os_detected)
            
            if result.ssh_port and result.ssh_port != 22:
                host.tags.append(f"ssh_port_{result.ssh_port}")
            
            self.inventory.add_host(host, group_name)
        
        log_info(f"Создан инвентори с {self.inventory.get_host_count()} хостами")
        
        return self.inventory
    
    def _dict_to_inventory(self, data: Dict[str, Any]) -> Inventory:
        """Конвертирует словарь в Inventory объект."""
        inventory = Inventory(
            version=data.get("version", "1.0"),
            updated=data.get("updated", time.strftime("%Y-%m-%d %H:%M:%S")),
            security=data.get("security", {})
        )
        
        groups_data = data.get("groups", {})
        for group_name, group_data in groups_data.items():
            if not isinstance(group_data, dict):
                continue
            
            group_vars = group_data.get("vars", {})
            group = HostGroup(name=group_name, vars=group_vars)
            
            hosts_data = group_data.get("hosts", [])
            for host_data in hosts_data:
                if not isinstance(host_data, dict):
                    continue
                
                host = HostEntry(
                    ip=host_data.get("ip"),
                    hostname=host_data.get("hostname"),
                    ssh_port=host_data.get("ssh_port", 22),
                    ssh_user=host_data.get("ssh_user", "root"),
                    ssh_key=host_data.get("ssh_key"),
                    ssh_password=host_data.get("ssh_password"),
                    profile=host_data.get("profile"),
                    os=host_data.get("os"),
                    tags=host_data.get("tags", []),
                    vars=host_data.get("vars", {}),
                    enabled=host_data.get("enabled", True),
                )
                group.add_host(host)
            
            inventory.groups[group_name] = group
        
        return inventory
    
    def print_summary(self) -> None:
        """Выводит сводку по инвентори."""
        if not self.inventory:
            print("Инвентори не загружен")
            return
        
        total_hosts = self.inventory.get_host_count()
        
        print("\n" + "="*60)
        print("ИНВЕНТОРИ")
        print("="*60)
        print(f"Версия: {self.inventory.version}")
        print(f"Обновлён: {self.inventory.updated}")
        print(f"Всего хостов: {total_hosts}")
        print(f"Групп: {len(self.inventory.groups)}")
        
        for group_name, group in self.inventory.groups.items():
            enabled_hosts = len(group.filter_hosts(enabled_only=True))
            print(f"\nГруппа: {group_name}")
            print(f"  Хостов: {enabled_hosts}/{len(group.hosts)}")
            
            if group.vars:
                print("  Переменные:")
                for key, value in group.vars.items():
                    print(f"    {key}: {value}")
        
        print("="*60 + "\n")
    
    def list_hosts(
        self,
        *,
        group: Optional[str] = None,
        tags: Optional[List[str]] = None,
        os_filter: Optional[str] = None,
        verbose: bool = False,
    ) -> None:
        """Выводит список хостов с учётом фильтров."""
        if not self.inventory:
            print("Инвентори не загружен")
            return
        
        hosts = self.inventory.get_all_hosts(
            group=group,
            tags=tags,
            os_filter=os_filter,
            enabled_only=True
        )
        
        if not hosts:
            print("Нет хостов, соответствующих фильтрам")
            return
        
        print(f"\nНайдено хостов: {len(hosts)}\n")
        print(f"{'IP':<15} {'Hostname':<30} {'Group':<15} {'OS':<15}")
        print("-"*75)
        
        for host, group_name in hosts:
            hostname = host.hostname or "-"
            os_name = host.os or "-"
            print(f"{host.ip:<15} {hostname:<30} {group_name:<15} {os_name:<15}")
            
            if verbose:
                print(f"  SSH: {host.ssh_user}@{host.ip}:{host.ssh_port}")
                if host.profile:
                    print(f"  Profile: {host.profile}")
                if host.tags:
                    print(f"  Tags: {', '.join(host.tags)}")
                if host.ssh_key:
                    print(f"  SSH Key: {host.ssh_key}")
                print()


def load_inventory(path: Path) -> Inventory:
    """Удобная функция для загрузки инвентори."""
    manager = InventoryManager(path)
    return manager.load()


def save_inventory(inventory: Inventory, path: Path) -> None:
    """Удобная функция для сохранения инвентори."""
    manager = InventoryManager()
    manager.inventory = inventory
    manager.save(path)
