"""Health check endpoint for Kubernetes probes and monitoring.

This module provides health check functionality for liveness and readiness probes.
"""

import sys
import json
from pathlib import Path
from typing import Dict, Any
from datetime import datetime


def check_system_health() -> Dict[str, Any]:
    """
    Perform comprehensive system health check.
    
    Returns:
        Dictionary with health status and details
    """
    health_status = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "checks": {}
    }
    
    # Check Python version
    python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    health_status["checks"]["python_version"] = {
        "status": "pass",
        "value": python_version,
        "required": ">=3.10"
    }
    
    if sys.version_info < (3, 10):
        health_status["checks"]["python_version"]["status"] = "fail"
        health_status["status"] = "unhealthy"
    
    # Check required modules
    required_modules = ["yaml", "jinja2", "colorama", "jsonschema"]
    for module_name in required_modules:
        try:
            __import__(module_name)
            health_status["checks"][f"module_{module_name}"] = {
                "status": "pass",
                "message": f"{module_name} is available"
            }
        except ImportError:
            health_status["checks"][f"module_{module_name}"] = {
                "status": "fail",
                "message": f"{module_name} is missing"
            }
            health_status["status"] = "unhealthy"
    
    # Check profiles directory
    profiles_dir = Path("profiles")
    if profiles_dir.exists() and profiles_dir.is_dir():
        profile_count = len(list(profiles_dir.rglob("*.yml")))
        health_status["checks"]["profiles"] = {
            "status": "pass",
            "count": profile_count,
            "path": str(profiles_dir.absolute())
        }
    else:
        health_status["checks"]["profiles"] = {
            "status": "fail",
            "message": "Profiles directory not found"
        }
        health_status["status"] = "unhealthy"
    
    # Check write permissions for results
    results_dir = Path("results")
    try:
        results_dir.mkdir(exist_ok=True)
        test_file = results_dir / ".health_check"
        test_file.touch()
        test_file.unlink()
        health_status["checks"]["results_writable"] = {
            "status": "pass",
            "path": str(results_dir.absolute())
        }
    except Exception as e:
        health_status["checks"]["results_writable"] = {
            "status": "fail",
            "message": str(e)
        }
        health_status["status"] = "unhealthy"
    
    return health_status


def check_readiness() -> Dict[str, Any]:
    """
    Check if the application is ready to serve requests.
    
    Returns:
        Dictionary with readiness status
    """
    readiness = {
        "ready": True,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "checks": {}
    }
    
    # Check if profiles are loaded
    profiles_dir = Path("profiles")
    if profiles_dir.exists():
        profile_files = list(profiles_dir.rglob("*.yml"))
        readiness["checks"]["profiles_available"] = {
            "status": "pass",
            "count": len(profile_files)
        }
    else:
        readiness["checks"]["profiles_available"] = {
            "status": "fail",
            "message": "No profiles found"
        }
        readiness["ready"] = False
    
    # Check critical dependencies
    try:
        import yaml
        import jinja2
        readiness["checks"]["dependencies"] = {
            "status": "pass",
            "message": "All critical dependencies loaded"
        }
    except ImportError as e:
        readiness["checks"]["dependencies"] = {
            "status": "fail",
            "message": f"Missing dependency: {e}"
        }
        readiness["ready"] = False
    
    return readiness


def health_check_handler(check_type: str = "liveness") -> int:
    """
    Handle health check request and return appropriate exit code.
    
    Args:
        check_type: Type of check - "liveness" or "readiness"
    
    Returns:
        Exit code: 0 for healthy, 1 for unhealthy
    """
    if check_type == "readiness":
        result = check_readiness()
        print(json.dumps(result, indent=2))
        return 0 if result["ready"] else 1
    else:  # liveness
        result = check_system_health()
        print(json.dumps(result, indent=2))
        return 0 if result["status"] == "healthy" else 1


def print_health_status():
    """Print health status in human-readable format."""
    health = check_system_health()
    
    print(f"\n🏥 SecAudit+ Health Check")
    print(f"{'='*50}")
    print(f"Status: {'✅ HEALTHY' if health['status'] == 'healthy' else '❌ UNHEALTHY'}")
    print(f"Timestamp: {health['timestamp']}")
    print(f"\nChecks:")
    
    for check_name, check_data in health["checks"].items():
        status_icon = "✅" if check_data["status"] == "pass" else "❌"
        print(f"  {status_icon} {check_name}: {check_data.get('message', check_data.get('value', 'OK'))}")
    
    print(f"{'='*50}\n")
    
    return 0 if health["status"] == "healthy" else 1
