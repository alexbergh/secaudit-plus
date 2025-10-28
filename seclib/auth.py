"""Authentication and authorization для SecAudit+."""

import hashlib
import hmac
import secrets
import time
from typing import Optional, Dict, List, Any
from dataclasses import dataclass
from enum import Enum


class Role(Enum):
    """User roles."""
    VIEWER = "viewer"
    AUDITOR = "auditor"
    ADMIN = "admin"


class AuthError(Exception):
    """Authentication/Authorization error."""
    pass


@dataclass
class User:
    """User information."""
    username: str
    roles: List[Role]
    metadata: Dict[str, Any] = None
    
    def has_role(self, role: Role) -> bool:
        """Check if user has specific role."""
        return role in self.roles
    
    def has_any_role(self, roles: List[Role]) -> bool:
        """Check if user has any of the specified roles."""
        return any(role in self.roles for role in roles)
    
    def can_view_results(self) -> bool:
        """Check if user can view audit results."""
        return self.has_any_role([Role.VIEWER, Role.AUDITOR, Role.ADMIN])
    
    def can_run_audit(self) -> bool:
        """Check if user can run audits."""
        return self.has_any_role([Role.AUDITOR, Role.ADMIN])
    
    def can_manage_users(self) -> bool:
        """Check if user can manage other users."""
        return self.has_role(Role.ADMIN)


class APIKeyAuth:
    """API Key authentication."""
    
    def __init__(self, keys: Dict[str, Dict[str, Any]]):
        """
        Initialize API key authenticator.
        
        Args:
            keys: Dictionary mapping API keys to user info
                  Format: {
                      "key_hash": {
                          "username": "ci-pipeline",
                          "roles": ["auditor"],
                          "metadata": {}
                      }
                  }
        """
        self.keys = keys
    
    @staticmethod
    def generate_key() -> str:
        """
        Generate a new API key.
        
        Returns:
            str: Random API key (hex string)
        """
        return secrets.token_hex(32)
    
    @staticmethod
    def hash_key(key: str) -> str:
        """
        Hash an API key for storage.
        
        Args:
            key: Plain API key
            
        Returns:
            str: SHA256 hash of the key
        """
        return hashlib.sha256(key.encode()).hexdigest()
    
    def authenticate(self, api_key: str) -> Optional[User]:
        """
        Authenticate using API key.
        
        Args:
            api_key: API key from request
            
        Returns:
            User object if authenticated, None otherwise
        """
        key_hash = self.hash_key(api_key)
        
        if key_hash not in self.keys:
            return None
        
        user_info = self.keys[key_hash]
        roles = [Role(r) for r in user_info.get("roles", [])]
        
        return User(
            username=user_info["username"],
            roles=roles,
            metadata=user_info.get("metadata", {})
        )


class JWTAuth:
    """JWT authentication (simplified)."""
    
    def __init__(self, secret: str, issuer: str = "secaudit", expiration: int = 86400):
        """
        Initialize JWT authenticator.
        
        Args:
            secret: Secret key for signing
            issuer: JWT issuer
            expiration: Token expiration in seconds (default 24h)
        """
        self.secret = secret
        self.issuer = issuer
        self.expiration = expiration
    
    def create_token(self, username: str, roles: List[Role]) -> str:
        """
        Create JWT token (simplified - use PyJWT in production).
        
        Args:
            username: Username
            roles: User roles
            
        Returns:
            str: JWT token
        """
        # В production используйте библиотеку PyJWT
        # Это упрощенная реализация для демонстрации
        
        payload = {
            "iss": self.issuer,
            "sub": username,
            "roles": [r.value for r in roles],
            "iat": int(time.time()),
            "exp": int(time.time()) + self.expiration
        }
        
        # Simplified signing (use PyJWT in production!)
        import json
        import base64
        
        header = base64.b64encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode()).decode()
        payload_encoded = base64.b64encode(json.dumps(payload).encode()).decode()
        
        signature = hmac.new(
            self.secret.encode(),
            f"{header}.{payload_encoded}".encode(),
            hashlib.sha256
        ).hexdigest()
        
        return f"{header}.{payload_encoded}.{signature}"
    
    def verify_token(self, token: str) -> Optional[User]:
        """
        Verify JWT token (simplified - use PyJWT in production).
        
        Args:
            token: JWT token
            
        Returns:
            User object if valid, None otherwise
        """
        try:
            import json
            import base64
            
            parts = token.split('.')
            if len(parts) != 3:
                return None
            
            header, payload_encoded, signature = parts
            
            # Verify signature
            expected_signature = hmac.new(
                self.secret.encode(),
                f"{header}.{payload_encoded}".encode(),
                hashlib.sha256
            ).hexdigest()
            
            if not hmac.compare_digest(signature, expected_signature):
                return None
            
            # Decode payload
            payload = json.loads(base64.b64decode(payload_encoded).decode())
            
            # Check expiration
            if payload.get("exp", 0) < time.time():
                return None
            
            # Check issuer
            if payload.get("iss") != self.issuer:
                return None
            
            # Create user
            roles = [Role(r) for r in payload.get("roles", [])]
            return User(
                username=payload["sub"],
                roles=roles,
                metadata={"token_issued_at": payload.get("iat")}
            )
            
        except Exception:
            return None


class AuthManager:
    """Unified authentication manager."""
    
    def __init__(self):
        """Initialize auth manager."""
        self.api_key_auth: Optional[APIKeyAuth] = None
        self.jwt_auth: Optional[JWTAuth] = None
    
    def configure_api_keys(self, keys: Dict[str, Dict[str, Any]]):
        """Configure API key authentication."""
        self.api_key_auth = APIKeyAuth(keys)
    
    def configure_jwt(self, secret: str, issuer: str = "secaudit", expiration: int = 86400):
        """Configure JWT authentication."""
        self.jwt_auth = JWTAuth(secret, issuer, expiration)
    
    def authenticate(self, credentials: Dict[str, str]) -> Optional[User]:
        """
        Authenticate user with provided credentials.
        
        Args:
            credentials: Dict with 'type' and credential data
                        Examples:
                        - {"type": "api_key", "key": "..."}
                        - {"type": "jwt", "token": "..."}
        
        Returns:
            User object if authenticated, None otherwise
        """
        cred_type = credentials.get("type")
        
        if cred_type == "api_key" and self.api_key_auth:
            return self.api_key_auth.authenticate(credentials.get("key", ""))
        
        elif cred_type == "jwt" and self.jwt_auth:
            return self.jwt_auth.verify_token(credentials.get("token", ""))
        
        return None
    
    def require_role(self, user: Optional[User], required_role: Role) -> User:
        """
        Require user to have specific role.
        
        Args:
            user: User object or None
            required_role: Required role
            
        Returns:
            User object if authorized
            
        Raises:
            AuthError: If not authenticated or not authorized
        """
        if user is None:
            raise AuthError("Authentication required")
        
        if not user.has_role(required_role):
            raise AuthError(f"Role '{required_role.value}' required")
        
        return user
    
    def require_any_role(self, user: Optional[User], required_roles: List[Role]) -> User:
        """
        Require user to have any of the specified roles.
        
        Args:
            user: User object or None
            required_roles: List of acceptable roles
            
        Returns:
            User object if authorized
            
        Raises:
            AuthError: If not authenticated or not authorized
        """
        if user is None:
            raise AuthError("Authentication required")
        
        if not user.has_any_role(required_roles):
            roles_str = ", ".join(r.value for r in required_roles)
            raise AuthError(f"One of roles required: {roles_str}")
        
        return user


# Global auth manager instance
auth_manager = AuthManager()


def get_auth_manager() -> AuthManager:
    """Get global auth manager instance."""
    return auth_manager
