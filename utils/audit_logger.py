"""Audit logging для SecAudit+."""

import json
import logging
import time
from datetime import datetime
from typing import Optional, Dict, Any
from pathlib import Path
from dataclasses import dataclass, asdict
from enum import Enum


class AuditEventType(Enum):
    """Types of audit events."""
    # Authentication events
    AUTH_SUCCESS = "auth.success"
    AUTH_FAILURE = "auth.failure"
    AUTH_LOGOUT = "auth.logout"
    
    # Audit execution events
    AUDIT_START = "audit.start"
    AUDIT_COMPLETE = "audit.complete"
    AUDIT_FAILED = "audit.failed"
    AUDIT_CANCELLED = "audit.cancelled"
    
    # Resource access events
    RESULTS_VIEW = "results.view"
    RESULTS_DOWNLOAD = "results.download"
    RESULTS_DELETE = "results.delete"
    
    # Configuration events
    CONFIG_VIEW = "config.view"
    CONFIG_UPDATE = "config.update"
    PROFILE_LOAD = "profile.load"
    
    # User management events
    USER_CREATE = "user.create"
    USER_UPDATE = "user.update"
    USER_DELETE = "user.delete"
    ROLE_ASSIGN = "role.assign"
    ROLE_REVOKE = "role.revoke"
    
    # System events
    SYSTEM_START = "system.start"
    SYSTEM_STOP = "system.stop"
    SYSTEM_ERROR = "system.error"


class AuditSeverity(Enum):
    """Severity levels for audit events."""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class AuditEvent:
    """Audit event."""
    timestamp: str
    event_type: str
    severity: str
    username: Optional[str]
    source_ip: Optional[str]
    action: str
    resource: Optional[str]
    result: str  # success, failure, error
    details: Dict[str, Any]
    session_id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)
    
    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict())


class AuditLogger:
    """
    Audit logger for security events.
    
    Logs all security-relevant events including:
    - Authentication attempts
    - Audit executions
    - Resource access
    - Configuration changes
    - User management
    """
    
    def __init__(
        self,
        log_file: Optional[Path] = None,
        log_level: str = "INFO",
        enable_syslog: bool = False,
        syslog_host: Optional[str] = None,
        syslog_port: int = 514,
    ):
        """
        Initialize audit logger.
        
        Args:
            log_file: Path to audit log file
            log_level: Minimum log level
            enable_syslog: Enable syslog output
            syslog_host: Syslog server host
            syslog_port: Syslog server port
        """
        self.log_file = log_file
        self.log_level = getattr(logging, log_level.upper())
        self.enable_syslog = enable_syslog
        self.syslog_host = syslog_host
        self.syslog_port = syslog_port
        
        # Setup logger
        self.logger = logging.getLogger("secaudit.audit")
        self.logger.setLevel(self.log_level)
        self.logger.propagate = False
        
        # File handler
        if self.log_file:
            self.log_file.parent.mkdir(parents=True, exist_ok=True)
            file_handler = logging.FileHandler(self.log_file)
            file_handler.setLevel(self.log_level)
            file_handler.setFormatter(
                logging.Formatter('%(message)s')  # JSON format
            )
            self.logger.addHandler(file_handler)
        
        # Syslog handler
        if self.enable_syslog and self.syslog_host:
            from logging.handlers import SysLogHandler
            syslog_handler = SysLogHandler(
                address=(self.syslog_host, self.syslog_port)
            )
            syslog_handler.setLevel(self.log_level)
            syslog_handler.setFormatter(
                logging.Formatter('secaudit: %(message)s')
            )
            self.logger.addHandler(syslog_handler)
    
    def log_event(
        self,
        event_type: AuditEventType,
        action: str,
        result: str,
        username: Optional[str] = None,
        source_ip: Optional[str] = None,
        resource: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        severity: AuditSeverity = AuditSeverity.INFO,
        session_id: Optional[str] = None,
    ):
        """
        Log an audit event.
        
        Args:
            event_type: Type of event
            action: Action performed
            result: Result (success, failure, error)
            username: Username who performed action
            source_ip: Source IP address
            resource: Resource affected
            details: Additional details
            severity: Event severity
            session_id: Session identifier
        """
        event = AuditEvent(
            timestamp=datetime.utcnow().isoformat() + "Z",
            event_type=event_type.value,
            severity=severity.value,
            username=username,
            source_ip=source_ip,
            action=action,
            resource=resource,
            result=result,
            details=details or {},
            session_id=session_id,
        )
        
        # Log as JSON
        self.logger.info(event.to_json())
    
    # Convenience methods for common events
    
    def log_auth_success(self, username: str, source_ip: Optional[str] = None, **kwargs):
        """Log successful authentication."""
        self.log_event(
            AuditEventType.AUTH_SUCCESS,
            action="authenticate",
            result="success",
            username=username,
            source_ip=source_ip,
            severity=AuditSeverity.INFO,
            **kwargs
        )
    
    def log_auth_failure(self, username: str, source_ip: Optional[str] = None, reason: str = "", **kwargs):
        """Log failed authentication."""
        self.log_event(
            AuditEventType.AUTH_FAILURE,
            action="authenticate",
            result="failure",
            username=username,
            source_ip=source_ip,
            details={"reason": reason},
            severity=AuditSeverity.WARNING,
            **kwargs
        )
    
    def log_audit_start(
        self,
        username: str,
        profile: str,
        level: str,
        source_ip: Optional[str] = None,
        **kwargs
    ):
        """Log audit start."""
        self.log_event(
            AuditEventType.AUDIT_START,
            action="start_audit",
            result="success",
            username=username,
            source_ip=source_ip,
            resource=profile,
            details={"level": level},
            severity=AuditSeverity.INFO,
            **kwargs
        )
    
    def log_audit_complete(
        self,
        username: str,
        profile: str,
        duration: float,
        score: float,
        checks_total: int,
        checks_passed: int,
        checks_failed: int,
        source_ip: Optional[str] = None,
        **kwargs
    ):
        """Log audit completion."""
        self.log_event(
            AuditEventType.AUDIT_COMPLETE,
            action="complete_audit",
            result="success",
            username=username,
            source_ip=source_ip,
            resource=profile,
            details={
                "duration_seconds": duration,
                "score": score,
                "checks_total": checks_total,
                "checks_passed": checks_passed,
                "checks_failed": checks_failed,
            },
            severity=AuditSeverity.INFO,
            **kwargs
        )
    
    def log_audit_failed(
        self,
        username: str,
        profile: str,
        error: str,
        source_ip: Optional[str] = None,
        **kwargs
    ):
        """Log audit failure."""
        self.log_event(
            AuditEventType.AUDIT_FAILED,
            action="run_audit",
            result="error",
            username=username,
            source_ip=source_ip,
            resource=profile,
            details={"error": error},
            severity=AuditSeverity.ERROR,
            **kwargs
        )
    
    def log_results_view(
        self,
        username: str,
        report_id: str,
        source_ip: Optional[str] = None,
        **kwargs
    ):
        """Log results viewing."""
        self.log_event(
            AuditEventType.RESULTS_VIEW,
            action="view_results",
            result="success",
            username=username,
            source_ip=source_ip,
            resource=report_id,
            severity=AuditSeverity.INFO,
            **kwargs
        )
    
    def log_config_update(
        self,
        username: str,
        config_key: str,
        old_value: Any,
        new_value: Any,
        source_ip: Optional[str] = None,
        **kwargs
    ):
        """Log configuration update."""
        self.log_event(
            AuditEventType.CONFIG_UPDATE,
            action="update_config",
            result="success",
            username=username,
            source_ip=source_ip,
            resource=config_key,
            details={
                "old_value": str(old_value),
                "new_value": str(new_value),
            },
            severity=AuditSeverity.WARNING,
            **kwargs
        )
    
    def log_user_create(
        self,
        admin_username: str,
        new_username: str,
        roles: list,
        source_ip: Optional[str] = None,
        **kwargs
    ):
        """Log user creation."""
        self.log_event(
            AuditEventType.USER_CREATE,
            action="create_user",
            result="success",
            username=admin_username,
            source_ip=source_ip,
            resource=new_username,
            details={"roles": roles},
            severity=AuditSeverity.WARNING,
            **kwargs
        )
    
    def log_role_assign(
        self,
        admin_username: str,
        target_username: str,
        role: str,
        source_ip: Optional[str] = None,
        **kwargs
    ):
        """Log role assignment."""
        self.log_event(
            AuditEventType.ROLE_ASSIGN,
            action="assign_role",
            result="success",
            username=admin_username,
            source_ip=source_ip,
            resource=target_username,
            details={"role": role},
            severity=AuditSeverity.WARNING,
            **kwargs
        )
    
    def log_system_error(
        self,
        error: str,
        details: Optional[Dict[str, Any]] = None,
        **kwargs
    ):
        """Log system error."""
        self.log_event(
            AuditEventType.SYSTEM_ERROR,
            action="system_operation",
            result="error",
            details={"error": error, **(details or {})},
            severity=AuditSeverity.ERROR,
            **kwargs
        )


# Global audit logger instance
_audit_logger: Optional[AuditLogger] = None


def get_audit_logger() -> AuditLogger:
    """Get global audit logger instance."""
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger(
            log_file=Path("/app/logs/audit.log"),
            log_level="INFO"
        )
    return _audit_logger


def configure_audit_logger(
    log_file: Optional[Path] = None,
    log_level: str = "INFO",
    enable_syslog: bool = False,
    syslog_host: Optional[str] = None,
    syslog_port: int = 514,
):
    """Configure global audit logger."""
    global _audit_logger
    _audit_logger = AuditLogger(
        log_file=log_file,
        log_level=log_level,
        enable_syslog=enable_syslog,
        syslog_host=syslog_host,
        syslog_port=syslog_port,
    )
