# modules/remote_executor.py
"""
Модуль удалённого выполнения аудитов на хостах через SSH.
Поддерживает параллельное выполнение и сбор результатов.
"""

from __future__ import annotations

import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from modules.inventory_manager import HostEntry, Inventory
from utils.logger import log_info, log_warn, log_fail


@dataclass
class RemoteAuditResult:
    """Результат удалённого аудита."""
    host: str
    ip: str
    success: bool
    duration: float = 0.0
    report_path: Optional[Path] = None
    error: Optional[str] = None
    summary: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Конвертация в словарь."""
        return {
            "host": self.host,
            "ip": self.ip,
            "success": self.success,
            "duration": self.duration,
            "report_path": str(self.report_path) if self.report_path else None,
            "error": self.error,
            "summary": self.summary,
        }


@dataclass
class RemoteExecutorConfig:
    """Конфигурация для удалённого выполнения."""
    inventory: Inventory
    output_dir: Path
    workers: int = 10
    profile: Optional[str] = None
    level: str = "baseline"
    fail_level: str = "none"
    evidence: bool = False
    timeout: int = 300  # 5 минут на один хост
    ssh_timeout: int = 30
    retry_count: int = 1
    
    def __post_init__(self):
        """Валидация параметров."""
        if self.workers < 1:
            raise ValueError("Число workers должно быть >= 1")
        if self.timeout < 10:
            raise ValueError("Timeout должен быть >= 10 секунд")


class RemoteExecutor:
    """Выполнитель удалённых аудитов."""
    
    def __init__(self, config: RemoteExecutorConfig):
        self.config = config
        self.results: List[RemoteAuditResult] = []
        self.secaudit_remote_path = "/tmp/secaudit-remote"
    
    def execute(
        self,
        *,
        group: Optional[str] = None,
        tags: Optional[List[str]] = None,
        os_filter: Optional[str] = None,
    ) -> List[RemoteAuditResult]:
        """
        Выполняет аудиты на удалённых хостах.
        
        Args:
            group: Фильтр по группе хостов
            tags: Фильтр по тегам
            os_filter: Фильтр по ОС
            
        Returns:
            Список результатов аудитов
        """
        # Получаем хосты для аудита
        hosts = self.config.inventory.get_all_hosts(
            group=group,
            tags=tags,
            os_filter=os_filter,
            enabled_only=True
        )
        
        if not hosts:
            log_warn("Нет хостов для аудита")
            return []
        
        total_hosts = len(hosts)
        log_info(f"Запуск удалённого аудита на {total_hosts} хостах с {self.config.workers} workers...")
        
        # Создаём директорию для отчётов
        self.config.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Параллельное выполнение
        with ThreadPoolExecutor(max_workers=self.config.workers) as executor:
            futures = {
                executor.submit(self._execute_on_host, host, group_name): (host, group_name)
                for host, group_name in hosts
            }
            
            completed = 0
            for future in as_completed(futures):
                completed += 1
                host, group_name = futures[future]
                
                try:
                    result = future.result()
                    self.results.append(result)
                    
                    status = "✓" if result.success else "✗"
                    log_info(
                        f"[{completed}/{total_hosts}] {status} {host.hostname or host.ip} "
                        f"({result.duration:.1f}s)"
                    )
                    
                except Exception as e:
                    log_fail(f"Критическая ошибка при аудите {host.ip}: {e}")
                    self.results.append(RemoteAuditResult(
                        host=host.hostname or host.ip,
                        ip=host.ip,
                        success=False,
                        error=str(e)
                    ))
        
        # Сводка
        successful = sum(1 for r in self.results if r.success)
        failed = len(self.results) - successful
        
        log_info(f"\nАудит завершён: {successful} успешно, {failed} с ошибками")
        
        return self.results
    
    def _execute_on_host(
        self,
        host: HostEntry,
        group_name: str,
    ) -> RemoteAuditResult:
        """
        Выполняет аудит на одном хосте.
        
        Args:
            host: Информация о хосте
            group_name: Имя группы хоста
            
        Returns:
            Результат аудита
        """
        start_time = time.time()
        hostname_clean = (host.hostname or host.ip).replace("/", "_").replace(":", "_")
        
        # Определяем профиль для использования
        profile = host.profile or self.config.profile
        if not profile:
            # Пытаемся определить по группе
            group = self.config.inventory.get_group(group_name)
            if group and group.vars:
                profile = group.vars.get("profile")
        
        if not profile:
            profile = "profiles/base/linux.yml"  # Fallback
        
        try:
            # Проверяем доступность хоста
            if not self._check_ssh_connection(host):
                return RemoteAuditResult(
                    host=host.hostname or host.ip,
                    ip=host.ip,
                    success=False,
                    duration=time.time() - start_time,
                    error="SSH подключение недоступно"
                )
            
            # Копируем необходимые файлы на удалённый хост
            if not self._prepare_remote_environment(host, profile):
                return RemoteAuditResult(
                    host=host.hostname or host.ip,
                    ip=host.ip,
                    success=False,
                    duration=time.time() - start_time,
                    error="Ошибка подготовки удалённого окружения"
                )
            
            # Запускаем аудит удалённо
            success, error = self._run_remote_audit(host, profile)
            
            if not success:
                return RemoteAuditResult(
                    host=host.hostname or host.ip,
                    ip=host.ip,
                    success=False,
                    duration=time.time() - start_time,
                    error=error or "Неизвестная ошибка при выполнении аудита"
                )
            
            # Собираем результаты
            report_path = self._collect_results(host, hostname_clean)
            
            # Читаем summary из отчёта
            summary = None
            if report_path and report_path.exists():
                summary = self._extract_summary(report_path)
            
            return RemoteAuditResult(
                host=host.hostname or host.ip,
                ip=host.ip,
                success=True,
                duration=time.time() - start_time,
                report_path=report_path,
                summary=summary
            )
            
        except Exception as e:
            return RemoteAuditResult(
                host=host.hostname or host.ip,
                ip=host.ip,
                success=False,
                duration=time.time() - start_time,
                error=f"Исключение: {str(e)}"
            )
        finally:
            # Очистка удалённого окружения
            self._cleanup_remote_environment(host)
    
    def _check_ssh_connection(self, host: HostEntry) -> bool:
        """Проверяет SSH подключение к хосту."""
        ssh_cmd = self._build_ssh_command(host, "echo 'test'")
        
        try:
            result = subprocess.run(
                ssh_cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=self.config.ssh_timeout,
                shell=False
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, OSError):
            return False
    
    def _prepare_remote_environment(self, host: HostEntry, profile: str) -> bool:
        """Подготавливает удалённое окружение для аудита."""
        try:
            # Создаём временную директорию на удалённом хосте
            ssh_cmd = self._build_ssh_command(
                host,
                f"mkdir -p {self.secaudit_remote_path}/profiles && "
                f"mkdir -p {self.secaudit_remote_path}/results"
            )
            
            result = subprocess.run(
                ssh_cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                timeout=self.config.ssh_timeout,
                shell=False
            )
            
            if result.returncode != 0:
                log_warn(f"Не удалось создать директории на {host.ip}: {result.stderr.decode()}")
                return False
            
            # Копируем профиль и зависимости
            profile_path = Path(profile)
            if not profile_path.exists():
                log_warn(f"Профиль {profile} не найден локально")
                return False
            
            # Копируем профиль
            if not self._scp_file(host, profile_path, f"{self.secaudit_remote_path}/profile.yml"):
                return False
            
            # Копируем директорию profiles/include если есть
            include_dir = Path("profiles/include")
            if include_dir.exists():
                if not self._scp_directory(host, include_dir, f"{self.secaudit_remote_path}/profiles/include"):
                    log_warn(f"Не удалось скопировать profiles/include на {host.ip}")
            
            return True
            
        except Exception as e:
            log_warn(f"Ошибка подготовки окружения на {host.ip}: {e}")
            return False
    
    def _run_remote_audit(self, host: HostEntry, profile: str) -> Tuple[bool, Optional[str]]:
        """Запускает аудит на удалённом хосте."""
        try:
            # Формируем команду аудита
            audit_cmd = (
                f"cd {self.secaudit_remote_path} && "
                f"python3 -m secaudit audit "
                f"--profile profile.yml "
                f"--level {self.config.level} "
                f"--fail-level {self.config.fail_level} "
            )
            
            if self.config.evidence:
                audit_cmd += "--evidence results/evidence "
            
            # Добавляем переменные из host.vars если есть
            if host.vars:
                for key, value in host.vars.items():
                    audit_cmd += f"--var {key}={value} "
            
            ssh_cmd = self._build_ssh_command(host, audit_cmd)
            
            result = subprocess.run(
                ssh_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=self.config.timeout,
                shell=False
            )
            
            # Код возврата 0 или 2 (найдены проблемы) считаем успешным выполнением
            if result.returncode in (0, 2):
                return True, None
            else:
                error_msg = result.stderr.decode('utf-8', errors='ignore')
                return False, f"Audit failed with code {result.returncode}: {error_msg[:200]}"
            
        except subprocess.TimeoutExpired:
            return False, f"Timeout ({self.config.timeout}s) при выполнении аудита"
        except Exception as e:
            return False, f"Исключение при запуске аудита: {str(e)}"
    
    def _collect_results(self, host: HostEntry, hostname_clean: str) -> Optional[Path]:
        """Собирает результаты аудита с удалённого хоста."""
        try:
            # Создаём директорию для хоста
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            host_dir = self.config.output_dir / "hosts" / hostname_clean / timestamp
            host_dir.mkdir(parents=True, exist_ok=True)
            
            # Копируем результаты
            remote_results = f"{self.secaudit_remote_path}/results"
            
            # Используем scp для копирования всей директории результатов
            scp_cmd = self._build_scp_command(
                host,
                f"{remote_results}/*",
                str(host_dir),
                download=True
            )
            
            result = subprocess.run(
                scp_cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                timeout=self.config.ssh_timeout * 2,
                shell=False
            )
            
            if result.returncode != 0:
                log_warn(f"Не удалось скопировать результаты с {host.ip}")
                return None
            
            # Создаём симлинк на последний отчёт
            latest_link = self.config.output_dir / "hosts" / hostname_clean / "latest"
            if latest_link.exists() or latest_link.is_symlink():
                latest_link.unlink()
            
            try:
                latest_link.symlink_to(timestamp, target_is_directory=True)
            except OSError:
                # На Windows может не работать, игнорируем
                pass
            
            # Возвращаем путь к основному отчёту
            report_json = host_dir / "report.json"
            return report_json if report_json.exists() else None
            
        except Exception as e:
            log_warn(f"Ошибка сбора результатов с {host.ip}: {e}")
            return None
    
    def _cleanup_remote_environment(self, host: HostEntry) -> None:
        """Очищает удалённое окружение после аудита."""
        try:
            ssh_cmd = self._build_ssh_command(host, f"rm -rf {self.secaudit_remote_path}")
            subprocess.run(
                ssh_cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=self.config.ssh_timeout,
                shell=False
            )
        except Exception:
            # Игнорируем ошибки очистки
            pass
    
    def _build_ssh_command(self, host: HostEntry, remote_command: str) -> List[str]:
        """Строит SSH команду для выполнения на хосте."""
        ssh_cmd = [
            "ssh",
            "-o", "StrictHostKeyChecking=no",
            "-o", "UserKnownHostsFile=/dev/null",
            "-o", f"ConnectTimeout={self.config.ssh_timeout}",
            "-p", str(host.ssh_port),
        ]
        
        if host.ssh_key:
            ssh_cmd.extend(["-i", host.ssh_key])
        
        # Если есть пароль, используем sshpass (если доступен)
        if host.ssh_password:
            ssh_cmd = ["sshpass", "-p", host.ssh_password] + ssh_cmd
        
        ssh_cmd.append(f"{host.ssh_user}@{host.ip}")
        ssh_cmd.append(remote_command)
        
        return ssh_cmd
    
    def _build_scp_command(
        self,
        host: HostEntry,
        source: str,
        destination: str,
        download: bool = False
    ) -> List[str]:
        """Строит SCP команду для копирования файлов."""
        scp_cmd = [
            "scp",
            "-o", "StrictHostKeyChecking=no",
            "-o", "UserKnownHostsFile=/dev/null",
            "-P", str(host.ssh_port),
            "-r",  # Рекурсивно
        ]
        
        if host.ssh_key:
            scp_cmd.extend(["-i", host.ssh_key])
        
        if host.ssh_password:
            scp_cmd = ["sshpass", "-p", host.ssh_password] + scp_cmd
        
        if download:
            # Скачиваем с удалённого хоста
            scp_cmd.append(f"{host.ssh_user}@{host.ip}:{source}")
            scp_cmd.append(destination)
        else:
            # Загружаем на удалённый хост
            scp_cmd.append(source)
            scp_cmd.append(f"{host.ssh_user}@{host.ip}:{destination}")
        
        return scp_cmd
    
    def _scp_file(self, host: HostEntry, local_path: Path, remote_path: str) -> bool:
        """Копирует файл на удалённый хост."""
        try:
            scp_cmd = self._build_scp_command(host, str(local_path), remote_path)
            result = subprocess.run(
                scp_cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                timeout=self.config.ssh_timeout,
                shell=False
            )
            return result.returncode == 0
        except Exception as e:
            log_warn(f"Ошибка копирования файла на {host.ip}: {e}")
            return False
    
    def _scp_directory(self, host: HostEntry, local_dir: Path, remote_path: str) -> bool:
        """Копирует директорию на удалённый хост."""
        return self._scp_file(host, local_dir, remote_path)
    
    def _extract_summary(self, report_path: Path) -> Optional[Dict[str, Any]]:
        """Извлекает summary из JSON отчёта."""
        try:
            with open(report_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get("summary")
        except Exception:
            return None
    
    def get_results(self) -> List[RemoteAuditResult]:
        """Возвращает результаты выполнения."""
        return self.results
    
    def generate_summary_report(self, output_path: Path) -> None:
        """Генерирует сводный отчёт по всем хостам."""
        if not self.results:
            log_warn("Нет результатов для генерации отчёта")
            return
        
        successful = [r for r in self.results if r.success]
        failed = [r for r in self.results if not r.success]
        
        summary = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "total_hosts": len(self.results),
            "successful": len(successful),
            "failed": len(failed),
            "results": [r.to_dict() for r in self.results]
        }
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        
        log_info(f"Сводный отчёт сохранён в {output_path}")


def execute_remote_audit(
    inventory: Inventory,
    output_dir: Path,
    *,
    workers: int = 10,
    profile: Optional[str] = None,
    level: str = "baseline",
    fail_level: str = "none",
    evidence: bool = False,
    group: Optional[str] = None,
    tags: Optional[List[str]] = None,
    os_filter: Optional[str] = None,
) -> List[RemoteAuditResult]:
    """
    Удобная функция для выполнения удалённого аудита.
    
    Args:
        inventory: Инвентори хостов
        output_dir: Директория для сохранения результатов
        workers: Количество параллельных workers
        profile: Профиль аудита
        level: Уровень строгости
        fail_level: Порог для fail
        evidence: Собирать ли evidence
        group: Фильтр по группе
        tags: Фильтр по тегам
        os_filter: Фильтр по ОС
        
    Returns:
        Список результатов аудитов
    """
    config = RemoteExecutorConfig(
        inventory=inventory,
        output_dir=output_dir,
        workers=workers,
        profile=profile,
        level=level,
        fail_level=fail_level,
        evidence=evidence,
    )
    
    executor = RemoteExecutor(config)
    results = executor.execute(group=group, tags=tags, os_filter=os_filter)
    
    # Генерируем сводный отчёт
    summary_path = output_dir / "summary.json"
    executor.generate_summary_report(summary_path)
    
    return results
