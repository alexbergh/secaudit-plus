# modules/network_scanner.py
"""
Модуль сканирования сети для обнаружения активных хостов.
Поддерживает ICMP ping, TCP port scanning и SSH banner detection.
"""

from __future__ import annotations

import socket
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from ipaddress import IPv4Address, IPv4Network, ip_network
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from utils.logger import log_info, log_warn, log_fail


@dataclass
class ScanResult:
    """Результат сканирования одного хоста."""
    ip: str
    hostname: Optional[str] = None
    is_alive: bool = False
    ssh_port: Optional[int] = None
    ssh_banner: Optional[str] = None
    os_detected: Optional[str] = None
    scan_duration: float = 0.0
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Конвертация в словарь для сериализации."""
        return {
            "ip": self.ip,
            "hostname": self.hostname,
            "is_alive": self.is_alive,
            "ssh_port": self.ssh_port,
            "ssh_banner": self.ssh_banner,
            "os_detected": self.os_detected,
            "scan_duration": self.scan_duration,
            "error": self.error,
        }


@dataclass
class ScanConfig:
    """Конфигурация для сканирования."""
    networks: List[str]
    ssh_ports: List[int] = field(default_factory=lambda: [22])
    timeout: int = 2
    workers: int = 50
    ping_method: str = "tcp"  # tcp, icmp, or both
    resolve_hostnames: bool = True
    detect_os: bool = True
    
    def __post_init__(self):
        """Валидация параметров."""
        if not self.networks:
            raise ValueError("Необходимо указать хотя бы одну сеть")
        if self.workers < 1:
            raise ValueError("Число workers должно быть >= 1")
        if self.timeout < 1:
            raise ValueError("Timeout должен быть >= 1")


class NetworkScanner:
    """Сканер сети для обнаружения хостов."""
    
    def __init__(self, config: ScanConfig):
        self.config = config
        self._results: List[ScanResult] = []
        self._lock = threading.Lock()
    
    def scan(self) -> List[ScanResult]:
        """
        Выполняет сканирование всех указанных сетей.
        
        Returns:
            Список результатов сканирования для каждого хоста
        """
        log_info(f"Начало сканирования {len(self.config.networks)} сетей...")
        
        # Собираем все IP адреса для сканирования
        all_ips: Set[str] = set()
        for network_str in self.config.networks:
            try:
                network = ip_network(network_str, strict=False)
                all_ips.update(str(ip) for ip in network.hosts())
            except ValueError as e:
                log_warn(f"Некорректная сеть {network_str}: {e}")
                continue
        
        total_ips = len(all_ips)
        log_info(f"Сканирование {total_ips} IP адресов с {self.config.workers} workers...")
        
        # Параллельное сканирование
        with ThreadPoolExecutor(max_workers=self.config.workers) as executor:
            futures = {executor.submit(self._scan_host, ip): ip for ip in all_ips}
            
            completed = 0
            for future in as_completed(futures):
                completed += 1
                if completed % 50 == 0 or completed == total_ips:
                    log_info(f"Прогресс: {completed}/{total_ips} ({completed*100//total_ips}%)")
                
                try:
                    result = future.result()
                    if result and result.is_alive:
                        with self._lock:
                            self._results.append(result)
                except Exception as e:
                    ip = futures[future]
                    log_warn(f"Ошибка при сканировании {ip}: {e}")
        
        alive_count = len(self._results)
        log_info(f"Сканирование завершено. Обнаружено {alive_count} активных хостов из {total_ips}")
        
        return self._results
    
    def _scan_host(self, ip: str) -> Optional[ScanResult]:
        """
        Сканирует отдельный хост.
        
        Args:
            ip: IP адрес хоста
            
        Returns:
            ScanResult или None если хост недоступен
        """
        start_time = time.time()
        result = ScanResult(ip=ip)
        
        # Проверка доступности
        is_alive = False
        if self.config.ping_method in ("tcp", "both"):
            is_alive = self._tcp_ping(ip, 22, self.config.timeout)
        
        if not is_alive and self.config.ping_method in ("icmp", "both"):
            is_alive = self._icmp_ping(ip, self.config.timeout)
        
        if not is_alive:
            return None
        
        result.is_alive = True
        
        # Резолв hostname
        if self.config.resolve_hostnames:
            result.hostname = self._resolve_hostname(ip)
        
        # Проверка SSH портов
        for port in self.config.ssh_ports:
            if self._check_ssh_port(ip, port, self.config.timeout):
                result.ssh_port = port
                
                # Получение SSH баннера
                if self.config.detect_os:
                    banner = self._get_ssh_banner(ip, port, self.config.timeout)
                    if banner:
                        result.ssh_banner = banner
                        result.os_detected = self._detect_os_from_banner(banner)
                break
        
        result.scan_duration = time.time() - start_time
        return result
    
    def _tcp_ping(self, ip: str, port: int, timeout: int) -> bool:
        """TCP пинг - проверка доступности через TCP коннект."""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            sock.connect((ip, port))
            sock.close()
            return True
        except (socket.timeout, socket.error, OSError):
            return False
    
    def _icmp_ping(self, ip: str, timeout: int) -> bool:
        """ICMP пинг через системную команду ping."""
        try:
            # Windows использует -n, Linux использует -c
            import platform
            param = "-n" if platform.system().lower() == "windows" else "-c"
            
            result = subprocess.run(
                ["ping", param, "1", "-w", str(timeout * 1000), ip],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=timeout + 1
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, OSError):
            return False
    
    def _resolve_hostname(self, ip: str) -> Optional[str]:
        """Резолвит hostname по IP адресу."""
        try:
            hostname, _, _ = socket.gethostbyaddr(ip)
            return hostname
        except (socket.herror, socket.gaierror, socket.timeout):
            return None
    
    def _check_ssh_port(self, ip: str, port: int, timeout: int) -> bool:
        """Проверяет доступность SSH порта."""
        return self._tcp_ping(ip, port, timeout)
    
    def _get_ssh_banner(self, ip: str, port: int, timeout: int) -> Optional[str]:
        """Получает SSH баннер для определения ОС."""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            sock.connect((ip, port))
            
            # SSH сервер отправляет баннер сразу после подключения
            banner = sock.recv(256).decode('utf-8', errors='ignore').strip()
            sock.close()
            
            return banner if banner.startswith('SSH-') else None
        except (socket.timeout, socket.error, OSError, UnicodeDecodeError):
            return None
    
    def _detect_os_from_banner(self, banner: str) -> Optional[str]:
        """Определяет ОС по SSH баннеру."""
        banner_lower = banner.lower()
        
        # Mapping известных паттернов в баннерах
        os_patterns = {
            'ubuntu': 'ubuntu',
            'debian': 'debian',
            'centos': 'centos',
            'rhel': 'rhel',
            'rocky': 'rocky',
            'almalinux': 'almalinux',
            'fedora': 'fedora',
            'opensuse': 'opensuse',
            'suse': 'suse',
            'arch': 'arch',
            'gentoo': 'gentoo',
            'alpine': 'alpine',
            'freebsd': 'freebsd',
            'openbsd': 'openbsd',
        }
        
        for pattern, os_name in os_patterns.items():
            if pattern in banner_lower:
                return os_name
        
        # Попытка извлечь версию из баннера
        # Пример: SSH-2.0-OpenSSH_8.2p1 Ubuntu-4ubuntu0.5
        if 'openssh' in banner_lower:
            parts = banner.split()
            for part in parts:
                part_lower = part.lower()
                for pattern, os_name in os_patterns.items():
                    if pattern in part_lower:
                        return os_name
        
        return None
    
    def get_results(self) -> List[ScanResult]:
        """Возвращает результаты сканирования."""
        return self._results
    
    def get_alive_hosts(self) -> List[ScanResult]:
        """Возвращает только активные хосты."""
        return [r for r in self._results if r.is_alive]
    
    def filter_by_os(self, os_name: str) -> List[ScanResult]:
        """Фильтрует результаты по ОС."""
        os_lower = os_name.lower()
        return [
            r for r in self._results 
            if r.os_detected and os_lower in r.os_detected.lower()
        ]
    
    def filter_by_ssh_available(self) -> List[ScanResult]:
        """Возвращает только хосты с доступным SSH."""
        return [r for r in self._results if r.ssh_port is not None]


def scan_networks(
    networks: List[str],
    *,
    ssh_ports: Optional[List[int]] = None,
    timeout: int = 2,
    workers: int = 50,
    ping_method: str = "tcp",
    resolve_hostnames: bool = True,
    detect_os: bool = True,
) -> List[ScanResult]:
    """
    Удобная функция для сканирования сетей.
    
    Args:
        networks: Список сетей в формате CIDR (например, ["192.168.1.0/24"])
        ssh_ports: Список SSH портов для проверки (по умолчанию [22])
        timeout: Таймаут для каждого хоста в секундах
        workers: Количество параллельных workers
        ping_method: Метод проверки доступности ("tcp", "icmp", "both")
        resolve_hostnames: Резолвить ли hostnames
        detect_os: Определять ли ОС по SSH баннеру
        
    Returns:
        Список результатов сканирования
    """
    config = ScanConfig(
        networks=networks,
        ssh_ports=ssh_ports or [22],
        timeout=timeout,
        workers=workers,
        ping_method=ping_method,
        resolve_hostnames=resolve_hostnames,
        detect_os=detect_os,
    )
    
    scanner = NetworkScanner(config)
    return scanner.scan()


def export_results_json(results: List[ScanResult], output_path: Path) -> None:
    """
    Экспортирует результаты в JSON файл.
    
    Args:
        results: Список результатов сканирования
        output_path: Путь к выходному файлу
    """
    import json
    
    data = {
        "scan_time": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total_hosts": len(results),
        "alive_hosts": len([r for r in results if r.is_alive]),
        "hosts": [r.to_dict() for r in results]
    }
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    log_info(f"Результаты экспортированы в {output_path}")


def export_results_yaml(results: List[ScanResult], output_path: Path) -> None:
    """
    Экспортирует результаты в YAML файл.
    
    Args:
        results: Список результатов сканирования
        output_path: Путь к выходному файлу
    """
    try:
        import yaml
    except ImportError:
        log_fail("PyYAML не установлен. Используйте: pip install PyYAML")
        return
    
    data = {
        "scan_time": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total_hosts": len(results),
        "alive_hosts": len([r for r in results if r.is_alive]),
        "hosts": [r.to_dict() for r in results]
    }
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True)
    
    log_info(f"Результаты экспортированы в {output_path}")


def print_scan_summary(results: List[ScanResult]) -> None:
    """Выводит краткую сводку результатов сканирования."""
    alive = [r for r in results if r.is_alive]
    ssh_available = [r for r in alive if r.ssh_port is not None]
    
    print("\n" + "="*60)
    print("РЕЗУЛЬТАТЫ СКАНИРОВАНИЯ")
    print("="*60)
    print(f"Всего хостов просканировано: {len(results)}")
    print(f"Активных хостов: {len(alive)}")
    print(f"Хостов с SSH: {len(ssh_available)}")
    
    if alive:
        print("\nАктивные хосты:")
        print(f"{'IP':<15} {'Hostname':<30} {'SSH Port':<10} {'OS':<15}")
        print("-"*70)
        for result in alive:
            hostname = result.hostname or "-"
            ssh_port = str(result.ssh_port) if result.ssh_port else "-"
            os_detected = result.os_detected or "-"
            print(f"{result.ip:<15} {hostname:<30} {ssh_port:<10} {os_detected:<15}")
    
    print("="*60 + "\n")
