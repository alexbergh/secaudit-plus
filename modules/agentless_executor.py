# modules/agentless_executor.py
"""
Agentless executor - выполнение аудита БЕЗ установки secaudit на целевых хостах.
Все команды выполняются через SSH, результаты анализируются на сервере.

Принцип работы:
1. Сервер загружает профиль локально
2. Для каждой проверки выполняет команду через SSH
3. Получает stdout/stderr/returncode
4. Анализирует результат локально (assert_logic)
5. Генерирует отчёт локально
"""

from __future__ import annotations

import json
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from modules.inventory_manager import HostEntry, Inventory
from utils.logger import log_info, log_warn, log_fail


@dataclass
class AgentlessAuditResult:
    """Результат agentless аудита одного хоста."""
    host: str
    ip: str
    success: bool
    duration: float = 0.0
    checks_total: int = 0
    checks_pass: int = 0
    checks_fail: int = 0
    checks_undef: int = 0
    score: float = 0.0
    results: List[Dict] = field(default_factory=list)
    error: Optional[str] = None
    
    def to_dict(self) -> Dict:
        """Конвертация в словарь."""
        return {
            "host": self.host,
            "ip": self.ip,
            "success": self.success,
            "duration": self.duration,
            "summary": {
                "total": self.checks_total,
                "pass": self.checks_pass,
                "fail": self.checks_fail,
                "undef": self.checks_undef,
                "score": self.score,
            },
            "results": self.results,
            "error": self.error,
        }


class AgentlessExecutor:
    """
    Agentless executor - выполняет аудит БЕЗ установки на целевых хостах.
    
    Преимущества:
    - Не требует установки на целевые хосты
    - Меньше attack surface
    - Централизованное управление
    - Типичный подход для security аудита
    """
    
    def __init__(
        self,
        inventory: Inventory,
        output_dir: Path,
        profile_path: str,
        level: str = "baseline",
        workers: int = 10,
        timeout: int = 30,
        ssh_timeout: int = 10,
    ):
        self.inventory = inventory
        self.output_dir = output_dir
        self.profile_path = profile_path
        self.level = level
        self.workers = workers
        self.timeout = timeout
        self.ssh_timeout = ssh_timeout
        self.results: List[AgentlessAuditResult] = []
    
    def execute(
        self,
        *,
        group: Optional[str] = None,
        tags: Optional[List[str]] = None,
        os_filter: Optional[str] = None,
    ) -> List[AgentlessAuditResult]:
        """
        Выполняет agentless аудит на хостах.
        
        Args:
            group: Фильтр по группе
            tags: Фильтр по тегам
            os_filter: Фильтр по ОС
            
        Returns:
            Список результатов аудитов
        """
        # Загружаем профиль ЛОКАЛЬНО на сервере
        log_info(f"[Agentless] Загрузка профиля: {self.profile_path}")
        profile = self._load_profile(self.profile_path)
        checks = profile.get("checks", [])
        
        # Фильтруем проверки по уровню строгости
        checks = self._filter_checks_by_level(checks)
        
        # Получаем хосты для аудита
        hosts = self.inventory.get_all_hosts(
            group=group,
            tags=tags,
            os_filter=os_filter,
            enabled_only=True
        )
        
        if not hosts:
            log_warn("[Agentless] Нет хостов для аудита")
            return []
        
        total_hosts = len(hosts)
        log_info(f"[Agentless] Аудит {total_hosts} хостов, {len(checks)} проверок, {self.workers} workers")
        
        # Создаём директорию для отчётов
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Параллельное выполнение на хостах
        with ThreadPoolExecutor(max_workers=self.workers) as executor:
            futures = {
                executor.submit(
                    self._execute_on_host, 
                    host, 
                    group_name, 
                    checks
                ): (host, group_name)
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
                        f"| Score: {result.score:.0f}/100 | "
                        f"Pass: {result.checks_pass} | Fail: {result.checks_fail} | "
                        f"({result.duration:.1f}s)"
                    )
                    
                except Exception as e:
                    log_fail(f"[Agentless] Критическая ошибка при аудите {host.ip}: {e}")
                    self.results.append(AgentlessAuditResult(
                        host=host.hostname or host.ip,
                        ip=host.ip,
                        success=False,
                        error=str(e)
                    ))
        
        # Генерируем сводный отчёт
        self._generate_summary_report()
        
        # Сводка
        successful = sum(1 for r in self.results if r.success)
        failed = len(self.results) - successful
        avg_score = sum(r.score for r in self.results if r.success) / max(successful, 1)
        
        log_info(f"\n[Agentless] Аудит завершён: {successful} успешно, {failed} с ошибками")
        log_info(f"[Agentless] Средний security score: {avg_score:.1f}/100")
        
        return self.results
    
    def _execute_on_host(
        self,
        host: HostEntry,
        group_name: str,
        checks: List[Dict],
    ) -> AgentlessAuditResult:
        """
        Выполняет аудит на одном хосте через SSH.
        
        Args:
            host: Информация о хосте
            group_name: Имя группы
            checks: Список проверок
            
        Returns:
            Результат аудита
        """
        start_time = time.time()
        hostname_clean = (host.hostname or host.ip).replace("/", "_").replace(":", "_")
        
        # Проверяем SSH доступность
        if not self._check_ssh_connection(host):
            return AgentlessAuditResult(
                host=host.hostname or host.ip,
                ip=host.ip,
                success=False,
                duration=time.time() - start_time,
                error="SSH подключение недоступно"
            )
        
        # Выполняем проверки
        results = []
        checks_pass = 0
        checks_fail = 0
        checks_undef = 0
        
        for check in checks:
            check_result = self._execute_check(host, check)
            results.append(check_result)
            
            result_status = check_result.get("result", "UNDEF")
            if result_status == "PASS":
                checks_pass += 1
            elif result_status == "FAIL":
                checks_fail += 1
            else:
                checks_undef += 1
        
        # Рассчитываем score
        total_checks = len(checks)
        score = (checks_pass / total_checks * 100) if total_checks > 0 else 0
        
        # Сохраняем отчёт для хоста
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        host_dir = self.output_dir / "hosts" / hostname_clean / timestamp
        host_dir.mkdir(parents=True, exist_ok=True)
        
        report_data = {
            "host": host.hostname or host.ip,
            "ip": host.ip,
            "group": group_name,
            "audit_time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "duration": time.time() - start_time,
            "summary": {
                "total": total_checks,
                "pass": checks_pass,
                "fail": checks_fail,
                "undef": checks_undef,
                "score": score,
            },
            "results": results,
        }
        
        # Сохраняем JSON отчёт
        report_json = host_dir / "report.json"
        with open(report_json, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, indent=2, ensure_ascii=False)
        
        # Создаём симлинк latest
        latest_link = self.output_dir / "hosts" / hostname_clean / "latest"
        if latest_link.exists() or latest_link.is_symlink():
            latest_link.unlink()
        try:
            latest_link.symlink_to(timestamp, target_is_directory=True)
        except OSError:
            pass  # Windows может не поддерживать symlinks
        
        return AgentlessAuditResult(
            host=host.hostname or host.ip,
            ip=host.ip,
            success=True,
            duration=time.time() - start_time,
            checks_total=total_checks,
            checks_pass=checks_pass,
            checks_fail=checks_fail,
            checks_undef=checks_undef,
            score=score,
            results=results,
        )
    
    def _execute_check(self, host: HostEntry, check: Dict) -> Dict:
        """
        Выполняет одну проверку через SSH.
        
        Args:
            host: Информация о хосте
            check: Определение проверки из профиля
            
        Returns:
            Результат проверки
        """
        check_id = check.get("id", "unknown")
        command = check.get("command", "")
        
        if not command:
            return {
                "id": check_id,
                "name": check.get("name", ""),
                "result": "UNDEF",
                "reason": "No command defined",
            }
        
        # Выполняем команду через SSH
        start_time = time.time()
        rc, stdout, stderr = self._run_ssh_command(host, command)
        duration = time.time() - start_time
        
        # Анализируем результат локально
        result_status, reason, asserts_results = self._evaluate_check_result(
            check, rc, stdout, stderr
        )
        
        return {
            "id": check_id,
            "name": check.get("name", ""),
            "module": check.get("module", "system"),
            "severity": check.get("severity", "low"),
            "command": command,
            "rc": rc,
            "output": stdout,
            "stderr": stderr,
            "result": result_status,
            "reason": reason,
            "duration": duration,
            "asserts": asserts_results,
        }
    
    def _run_ssh_command(self, host: HostEntry, command: str) -> Tuple[int, str, str]:
        """
        Выполняет команду через SSH и возвращает результат.
        
        Args:
            host: Информация о хосте
            command: Команда для выполнения
            
        Returns:
            (return_code, stdout, stderr)
        """
        ssh_cmd = self._build_ssh_command(host, command)
        
        try:
            result = subprocess.run(
                ssh_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=self.timeout,
                shell=False
            )
            
            stdout = result.stdout.decode('utf-8', errors='ignore')
            stderr = result.stderr.decode('utf-8', errors='ignore')
            
            return result.returncode, stdout, stderr
            
        except subprocess.TimeoutExpired:
            return -1, "", f"Timeout ({self.timeout}s)"
        except Exception as e:
            return -1, "", f"Error: {str(e)}"
    
    def _build_ssh_command(self, host: HostEntry, remote_command: str) -> List[str]:
        """Строит SSH команду."""
        ssh_cmd = [
            "ssh",
            "-o", "StrictHostKeyChecking=no",
            "-o", "UserKnownHostsFile=/dev/null",
            "-o", f"ConnectTimeout={self.ssh_timeout}",
            "-p", str(host.ssh_port),
        ]
        
        if host.ssh_key:
            ssh_cmd.extend(["-i", host.ssh_key])
        
        if host.ssh_password:
            ssh_cmd = ["sshpass", "-p", host.ssh_password] + ssh_cmd
        
        ssh_cmd.append(f"{host.ssh_user}@{host.ip}")
        ssh_cmd.append(remote_command)
        
        return ssh_cmd
    
    def _check_ssh_connection(self, host: HostEntry) -> bool:
        """Проверяет SSH подключение."""
        ssh_cmd = self._build_ssh_command(host, "echo test")
        
        try:
            result = subprocess.run(
                ssh_cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=self.ssh_timeout,
                shell=False
            )
            return result.returncode == 0
        except:
            return False
    
    def _evaluate_check_result(
        self,
        check: Dict,
        rc: int,
        stdout: str,
        stderr: str
    ) -> Tuple[str, str, List[Dict]]:
        """
        Анализирует результат проверки локально на сервере.
        Простая реализация для MVP - сравнение с ожидаемым значением.
        
        Args:
            check: Определение проверки
            rc: Return code команды
            stdout: Стандартный вывод
            stderr: Ошибки
            
        Returns:
            (status, reason, asserts_results)
        """
        try:
            expect = check.get("expect", "")
            assert_type = check.get("assert_type", "exact")
            output = stdout.strip()
            
            # Простая логика оценки
            if assert_type == "exact":
                if output == expect:
                    return "PASS", f"exact match '{expect}'", [{"type": "exact", "value": expect, "status": "PASS"}]
                else:
                    return "FAIL", f"got '{output}' != expect '{expect}'", [{"type": "exact", "value": expect, "status": "FAIL"}]
            
            elif assert_type == "contains":
                if expect in output:
                    return "PASS", f"contains '{expect}'", [{"type": "contains", "value": expect, "status": "PASS"}]
                else:
                    return "FAIL", f"'{expect}' not found in output", [{"type": "contains", "value": expect, "status": "FAIL"}]
            
            elif assert_type == "not_contains":
                if expect not in output:
                    return "PASS", f"does not contain '{expect}'", [{"type": "not_contains", "value": expect, "status": "PASS"}]
                else:
                    return "FAIL", f"'{expect}' unexpectedly found", [{"type": "not_contains", "value": expect, "status": "FAIL"}]
            
            elif assert_type == "rc":
                expected_rc = int(expect)
                if rc == expected_rc:
                    return "PASS", f"rc={rc} as expected", [{"type": "rc", "value": expect, "status": "PASS"}]
                else:
                    return "FAIL", f"rc={rc}, expected {expected_rc}", [{"type": "rc", "value": expect, "status": "FAIL"}]
            
            else:
                # Если нет expect, считаем PASS если rc==0
                if rc == 0:
                    return "PASS", "command succeeded", []
                else:
                    return "FAIL", f"command failed with rc={rc}", []
                    
        except Exception as e:
            return "UNDEF", f"Evaluation error: {str(e)}", []
    
    def _load_profile(self, profile_path: str) -> Dict:
        """Загружает профиль с диска."""
        import yaml
        
        with open(profile_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f) or {}
    
    def _filter_checks_by_level(self, checks: List[Dict]) -> List[Dict]:
        """Фильтрует проверки по уровню строгости."""
        level_hierarchy = {
            "baseline": ["baseline"],
            "strict": ["baseline", "strict"],
            "paranoid": ["baseline", "strict", "paranoid"],
        }
        
        allowed_levels = level_hierarchy.get(self.level, ["baseline"])
        
        return [
            check for check in checks
            if check.get("level", "baseline") in allowed_levels
        ]
    
    def _generate_summary_report(self):
        """Генерирует сводный отчёт по всем хостам."""
        summary_data = {
            "audit_time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "total_hosts": len(self.results),
            "successful": sum(1 for r in self.results if r.success),
            "failed": sum(1 for r in self.results if not r.success),
            "average_score": sum(r.score for r in self.results if r.success) / max(sum(1 for r in self.results if r.success), 1),
            "hosts": [r.to_dict() for r in self.results]
        }
        
        summary_path = self.output_dir / "summary.json"
        with open(summary_path, 'w', encoding='utf-8') as f:
            json.dump(summary_data, f, indent=2, ensure_ascii=False)
        
        log_info(f"[Agentless] Сводный отчёт: {summary_path}")


def execute_agentless_audit(
    inventory: Inventory,
    output_dir: Path,
    profile_path: str,
    *,
    level: str = "baseline",
    workers: int = 10,
    timeout: int = 30,
    group: Optional[str] = None,
    tags: Optional[List[str]] = None,
    os_filter: Optional[str] = None,
) -> List[AgentlessAuditResult]:
    """
    Удобная функция для agentless аудита.
    
    Args:
        inventory: Инвентори хостов
        output_dir: Директория для результатов
        profile_path: Путь к профилю
        level: Уровень строгости
        workers: Количество workers
        timeout: Таймаут на команду
        group: Фильтр по группе
        tags: Фильтр по тегам
        os_filter: Фильтр по ОС
        
    Returns:
        Список результатов
    """
    executor = AgentlessExecutor(
        inventory=inventory,
        output_dir=output_dir,
        profile_path=profile_path,
        level=level,
        workers=workers,
        timeout=timeout,
    )
    
    return executor.execute(group=group, tags=tags, os_filter=os_filter)
