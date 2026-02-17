"""
Core Authentication Module

Provides API key management and RBAC (Role-Based Access Control) functionality.
This module handles the core authentication logic independent of the web framework.
"""

import os
import secrets
import hashlib
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any, Set
from enum import Enum
from dataclasses import dataclass, asdict, field
from pathlib import Path

from passlib.context import CryptContext
from jose import JWTError, jwt
from fastapi import HTTPException, status, Depends, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field

from astraguard.logging_config import get_logger
from core.audit_logger import get_audit_logger, AuditEventType
from core.secrets import get_secret

# Constants
API_KEY_LENGTH = 32
JWT_SECRET_KEY_MIN_LENGTH = 32
ENCRYPTION_KEY_LENGTH = 32
DEFAULT_JWT_EXPIRATION_HOURS = 24
DEFAULT_API_KEY_EXPIRATION_DAYS = 365

# File paths
AUTH_DATA_DIR = Path("data/auth")
AUTH_DATA_DIR.mkdir(parents=True, exist_ok=True)
USERS_FILE = AUTH_DATA_DIR / "users.json"
API_KEYS_FILE = AUTH_DATA_DIR / "api_keys.json"
ENCRYPTION_KEY_FILE = AUTH_DATA_DIR / "encryption.key"

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT Security
security = HTTPBearer()

logger = get_logger(__name__)


class UserRole(str, Enum):
    """User roles with hierarchical permissions."""
    ADMIN = "admin"      # Full system access including user management
    OPERATOR = "operator"  # Full operational access (telemetry, phase changes)
    ANALYST = "analyst"   # Read-only access (status, history, monitoring)


class Permission(str, Enum):
    """Granular permissions for RBAC."""
    # System management
    MANAGE_USERS = "manage_users"
    SYSTEM_CONFIG = "system_config"

    # Operational
    SUBMIT_TELEMETRY = "submit_telemetry"
    UPDATE_PHASE = "update_phase"
    MANAGE_MEMORY = "manage_memory"

    # Monitoring/Read-only
    READ_STATUS = "read_status"
    READ_HISTORY = "read_history"
    READ_METRICS = "read_metrics"


# Role-based permissions mapping
ROLE_PERMISSIONS = {
    UserRole.ADMIN: [
        Permission.MANAGE_USERS,
        Permission.SYSTEM_CONFIG,
        Permission.SUBMIT_TELEMETRY,
        Permission.UPDATE_PHASE,
        Permission.MANAGE_MEMORY,
        Permission.READ_STATUS,
        Permission.READ_HISTORY,
        Permission.READ_METRICS,
    ],
    UserRole.OPERATOR: [
        Permission.SUBMIT_TELEMETRY,
        Permission.UPDATE_PHASE,
        Permission.MANAGE_MEMORY,
        Permission.READ_STATUS,
        Permission.READ_HISTORY,
        Permission.READ_METRICS,
    ],
    UserRole.ANALYST: [
        Permission.READ_STATUS,
        Permission.READ_HISTORY,
        Permission.READ_METRICS,
    ],
}


@dataclass
class User:
    """User account information."""
    id: str
    username: str
    email: str
    role: UserRole
    created_at: datetime
    last_login: Optional[datetime] = None
    is_active: bool = True
    hashed_password: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        data = asdict(self)
        data['created_at'] = self.created_at.isoformat()
        if self.last_login:
            data['last_login'] = self.last_login.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'User':
        """Create from dictionary."""
        data = data.copy()
        data['created_at'] = datetime.fromisoformat(data['created_at'])
        if data.get('last_login'):
            data['last_login'] = datetime.fromisoformat(data['last_login'])
        if isinstance(data.get('role'), str):
            data['role'] = UserRole(data['role'])
        return cls(**data)


@dataclass
class APIKey:
    """API key with metadata."""
    key: str
    name: str
    created_at: datetime
    id: str = ""
    user_id: str = ""
    hashed_key: str = ""
    expires_at: Optional[datetime] = None
    last_used: Optional[datetime] = None
    permissions: Set[str] = field(default_factory=lambda: {"read", "write"})
    rate_limit: int = 1000
    is_active: bool = True
    metadata: Dict[str, str] = field(default_factory=dict)

    def is_expired(self) -> bool:
        """Check if this key has expired."""
        if self.expires_at is None:
            return False
        return datetime.now() > self.expires_at

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            'key': self.key,
            'name': self.name,
            'id': self.id,
            'user_id': self.user_id,
            'hashed_key': self.hashed_key,
            'created_at': self.created_at.isoformat(),
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'last_used': self.last_used.isoformat() if self.last_used else None,
            'permissions': list(self.permissions),
            'rate_limit': self.rate_limit,
            'is_active': self.is_active,
            'metadata': self.metadata,
        }


class APIKeyManager:
    """
    Manages authentication, authorization, API keys, users, and JWT tokens.

    Features:
    - User account management with password hashing
    - API key generation with SHA-256 hashing
    - JWT token creation and validation
    - Role-based access control (RBAC)
    - Rate limiting per API key
    - Audit logging for security events
    """

    def __init__(self, keys_file: str = "config/api_keys.json"):
        self.logger = get_logger(__name__)
        self.keys_file = keys_file

        # Simple key store (loaded from JSON)
        self.api_keys: Dict[str, APIKey] = {}
        self.key_hashes: Dict[str, str] = {}
        self.rate_limits: Dict[str, List[datetime]] = {}

        # User and API key stores (for RBAC/JWT auth)
        self._users: Dict[str, User] = {}
        self._api_keys: Dict[str, APIKey] = {}

        # JWT secret
        self._jwt_secret = self._get_jwt_secret()

        # Load existing data
        self._load_keys()
        self._load_users()

        # Create default key if none exist (for development)
        if not self.api_keys and not self._api_keys:
            self._create_default_key()

    def _load_keys(self) -> None:
        """Load API keys from file."""
        if os.path.exists(self.keys_file):
            try:
                with open(self.keys_file, 'r') as f:
                    data = json.load(f)

                for key_data in data.get('keys', []):
                    created_at = datetime.fromisoformat(key_data['created_at'])
                    expires_at = None
                    if key_data.get('expires_at'):
                        expires_at = datetime.fromisoformat(key_data['expires_at'])
                    last_used = None
                    if key_data.get('last_used'):
                        last_used = datetime.fromisoformat(key_data['last_used'])

                    key = APIKey(
                        key=key_data['key'],
                        name=key_data['name'],
                        id=key_data.get('id', ''),
                        user_id=key_data.get('user_id', ''),
                        hashed_key=key_data.get('hashed_key', ''),
                        created_at=created_at,
                        expires_at=expires_at,
                        last_used=last_used,
                        permissions=set(key_data.get('permissions', ['read', 'write'])),
                        rate_limit=key_data.get('rate_limit', 1000),
                        is_active=key_data.get('is_active', True),
                        metadata=key_data.get('metadata', {})
                    )

                    self.api_keys[key.key] = key
                    self.key_hashes[hashlib.sha256(key.key.encode()).hexdigest()] = key.key

                    # Also store in _api_keys by id if available
                    if key.id:
                        self._api_keys[key.id] = key

                self.logger.info(f"Loaded {len(self.api_keys)} API keys from {self.keys_file}")

            except Exception as e:
                self.logger.error(f"Failed to load API keys: {e}")
                self._create_default_key()

    def _load_users(self) -> None:
        """Load users from file."""
        if USERS_FILE.exists():
            try:
                with open(USERS_FILE, 'r') as f:
                    data = json.load(f)
                for user_data in data.get('users', []):
                    user = User.from_dict(user_data)
                    self._users[user.id] = user
                self.logger.info(f"Loaded {len(self._users)} users")
            except Exception as e:
                self.logger.error(f"Failed to load users: {e}")

    def _save_keys(self) -> None:
        """Save API keys to file."""
        try:
            os.makedirs(os.path.dirname(self.keys_file), exist_ok=True)
            data = {
                'keys': [key.to_dict() for key in self.api_keys.values()]
            }
            with open(self.keys_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            self.logger.error(f"Failed to save API keys: {e}")

    def _save_users(self) -> None:
        """Save users to file."""
        try:
            AUTH_DATA_DIR.mkdir(parents=True, exist_ok=True)
            data = {
                'users': [user.to_dict() for user in self._users.values()]
            }
            with open(USERS_FILE, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            self.logger.error(f"Failed to save users: {e}")

    def _create_default_key(self) -> None:
        """Create a default API key for development."""
        default_key = secrets.token_urlsafe(32)
        key_id = secrets.token_urlsafe(8)
        key_obj = APIKey(
            key=default_key,
            name="default-dev-key",
            id=key_id,
            hashed_key=hashlib.sha256(default_key.encode()).hexdigest(),
            created_at=datetime.now(),
            permissions={"read", "write", "admin"},
            rate_limit=10000,
            metadata={"environment": "development", "auto_generated": "true"}
        )
        self.api_keys[default_key] = key_obj
        self._api_keys[key_id] = key_obj
        self.key_hashes[hashlib.sha256(default_key.encode()).hexdigest()] = default_key
        self._save_keys()
        self.logger.info("Created default API key for development")

    def _get_jwt_secret(self) -> str:
        """Get JWT secret key from secure secrets storage."""
        try:
            secret = get_secret("jwt_secret_key")
            if secret and len(secret) >= JWT_SECRET_KEY_MIN_LENGTH:
                return secret
        except (KeyError, ValueError):
            pass

        # Generate a secure random secret
        secret = secrets.token_urlsafe(32)
        self.logger = get_logger(__name__)
        self.logger.info("Generated new JWT secret key")
        return secret

    def _hash_api_key(self, api_key: str) -> str:
        """Hash API key for storage."""
        return hashlib.sha256(api_key.encode()).hexdigest()

    def _verify_api_key(self, provided_key: str, stored_hash: str) -> bool:
        """Verify API key against stored hash."""
        return secrets.compare_digest(self._hash_api_key(provided_key), stored_hash)

    # ---- User Management ----

    def create_user(self, username: str, email: str, role: UserRole, password: Optional[str] = None) -> User:
        """Create a new user account."""
        if any(u.username == username for u in self._users.values()):
            raise ValueError(f"User {username} already exists")

        user_id = secrets.token_urlsafe(16)
        hashed_password = pwd_context.hash(password) if password else None

        user = User(
            id=user_id,
            username=username,
            email=email,
            role=role,
            created_at=datetime.now(),
            hashed_password=hashed_password,
        )

        self._users[user_id] = user
        self._save_users()

        self.logger.info(f"User created: {username} (role={role.value})")

        audit_logger = get_audit_logger()
        audit_logger.log_event(
            AuditEventType.USER_CREATED,
            user_id=user_id,
            resource="user",
            action="create",
            details={"username": username, "email": email, "role": role.value}
        )

        return user

    def get_user(self, user_id: str) -> Optional[User]:
        """Get user by ID."""
        return self._users.get(user_id)

    def update_user_last_login(self, user_id: str) -> None:
        """Update user's last login timestamp."""
        user = self._users.get(user_id)
        if user:
            user.last_login = datetime.now()
            self._save_users()

    def authenticate_user(self, username: str, password: str) -> str:
        """Authenticate user with username and password, return JWT token."""
        user = None
        for u in self._users.values():
            if u.username == username and u.is_active:
                user = u
                break

        if user is None or user.hashed_password is None:
            audit_logger = get_audit_logger()
            audit_logger.log_event(
                AuditEventType.AUTHENTICATION_FAILURE,
                resource="user",
                action="login",
                status="failure",
                details={"reason": "user_not_found", "username": username}
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials"
            )

        if not pwd_context.verify(password, user.hashed_password):
            audit_logger = get_audit_logger()
            audit_logger.log_event(
                AuditEventType.AUTHENTICATION_FAILURE,
                resource="user",
                action="login",
                status="failure",
                details={"reason": "invalid_password", "username": username}
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials"
            )

        self.update_user_last_login(user.id)
        token = self.create_jwt_token(user)

        audit_logger = get_audit_logger()
        audit_logger.log_event(
            AuditEventType.AUTHENTICATION_SUCCESS,
            user_id=user.id,
            resource="user",
            action="login",
            details={"username": username}
        )

        return token

    # ---- API Key Management ----

    def create_api_key(
        self,
        user_id: str,
        name: str,
        permissions: Optional[Set[str]] = None,
        expires_in_days: Optional[int] = None,
        rate_limit: int = 1000
    ) -> APIKey:
        """Create a new API key for a user."""
        if permissions is None:
            permissions = {"read", "write"}

        key_value = secrets.token_urlsafe(32)
        key_id = secrets.token_urlsafe(8)
        expires_at = None
        if expires_in_days:
            expires_at = datetime.now() + timedelta(days=expires_in_days)

        api_key_obj = APIKey(
            key=key_value,
            name=name,
            id=key_id,
            user_id=user_id,
            hashed_key=self._hash_api_key(key_value),
            created_at=datetime.now(),
            expires_at=expires_at,
            permissions=permissions,
            rate_limit=rate_limit,
        )

        self.api_keys[key_value] = api_key_obj
        self._api_keys[key_id] = api_key_obj
        self.key_hashes[self._hash_api_key(key_value)] = key_value
        self._save_keys()

        self.logger.info(f"API key created: {name} for user {user_id}")

        audit_logger = get_audit_logger()
        audit_logger.log_event(
            AuditEventType.API_KEY_CREATED,
            user_id=user_id,
            resource="api_key",
            action="create",
            details={"key_id": key_id, "name": name, "rate_limit": rate_limit}
        )

        return api_key_obj

    def validate_key(self, api_key: str) -> APIKey:
        """
        Validate an API key and return its details.

        Raises:
            ValueError: If key is invalid, expired, or inactive
        """
        if api_key not in self.api_keys:
            raise ValueError("Invalid API key")

        key = self.api_keys[api_key]

        if not key.is_active:
            raise ValueError("API key has been revoked")

        if key.is_expired():
            raise ValueError("API key has expired")

        return key

    def validate_api_key(self, provided_key: str) -> Optional[Tuple[User, APIKey]]:
        """Validate API key and return user and key info."""
        # Check direct key match first
        if provided_key in self.api_keys:
            api_key = self.api_keys[provided_key]
            if api_key.is_active and not api_key.is_expired():
                user = self._users.get(api_key.user_id)
                if user and user.is_active:
                    api_key.last_used = datetime.now()
                    self._save_keys()
                    self.update_user_last_login(user.id)

                    audit_logger = get_audit_logger()
                    audit_logger.log_event(
                        AuditEventType.AUTHENTICATION_SUCCESS,
                        user_id=user.id,
                        resource="api_key",
                        action="validate",
                        details={"key_id": api_key.id, "key_name": api_key.name}
                    )
                    return user, api_key

        # Check by hashed key
        for api_key in self._api_keys.values():
            if api_key.is_active and not api_key.is_expired() and api_key.hashed_key:
                if self._verify_api_key(provided_key, api_key.hashed_key):
                    user = self._users.get(api_key.user_id)
                    if user and user.is_active:
                        api_key.last_used = datetime.now()
                        self._save_keys()
                        self.update_user_last_login(user.id)

                        audit_logger = get_audit_logger()
                        audit_logger.log_event(
                            AuditEventType.AUTHENTICATION_SUCCESS,
                            user_id=user.id,
                            resource="api_key",
                            action="validate",
                            details={"key_id": api_key.id, "key_name": api_key.name}
                        )
                        return user, api_key

        self.logger.warning("API key validation failed")
        audit_logger = get_audit_logger()
        audit_logger.log_event(
            AuditEventType.AUTHENTICATION_FAILURE,
            resource="api_key",
            action="validate",
            status="failure",
            details={"reason": "invalid_api_key"}
        )
        return None

    def revoke_api_key(self, key_id: str, user_id: str) -> None:
        """Revoke an API key."""
        api_key = self._api_keys.get(key_id)
        if api_key is None:
            # Search by key_id in api_keys
            for k in self.api_keys.values():
                if k.id == key_id:
                    api_key = k
                    break

        if api_key is None:
            raise ValueError(f"API key {key_id} not found")

        if api_key.user_id and api_key.user_id != user_id:
            raise ValueError("Unauthorized to revoke this API key")

        api_key.is_active = False
        self._save_keys()

        self.logger.info(f"API key revoked: {key_id}")

        audit_logger = get_audit_logger()
        audit_logger.log_event(
            AuditEventType.API_KEY_REVOKED,
            user_id=user_id,
            resource="api_key",
            action="revoke",
            details={"key_id": key_id, "key_name": api_key.name}
        )

    def get_user_api_keys(self, user_id: str) -> List[APIKey]:
        """List all API keys for a user."""
        return [key for key in self.api_keys.values() if key.user_id == user_id]

    def list_user_api_keys(self, user_id: str) -> List[APIKey]:
        """List all API keys for a user (alias)."""
        return self.get_user_api_keys(user_id)

    def check_rate_limit(self, api_key: str) -> None:
        """Check if the API key has exceeded its rate limit."""
        if api_key not in self.api_keys:
            return

        key = self.api_keys[api_key]
        now = datetime.now()

        if api_key not in self.rate_limits:
            self.rate_limits[api_key] = []

        cutoff = now - timedelta(hours=1)
        self.rate_limits[api_key] = [
            ts for ts in self.rate_limits[api_key] if ts > cutoff
        ]

        if len(self.rate_limits[api_key]) >= key.rate_limit:
            raise ValueError(f"Rate limit exceeded. Maximum {key.rate_limit} requests per hour.")

        self.rate_limits[api_key].append(now)

    def has_permission(self, api_key: str, permission: str) -> bool:
        """Check if an API key has a specific permission."""
        try:
            key = self.validate_key(api_key)
            return permission in key.permissions
        except ValueError:
            return False

    def list_keys(self) -> List[Dict]:
        """List all API keys (without showing the actual key values)."""
        return [
            {
                "name": key.name,
                "created_at": key.created_at.isoformat(),
                "expires_at": key.expires_at.isoformat() if key.expires_at else None,
                "permissions": list(key.permissions),
                "rate_limit": key.rate_limit,
                "is_active": key.is_active,
                "metadata": key.metadata
            }
            for key in self.api_keys.values()
        ]

    # ---- JWT & Permission Management ----

    def check_permission(self, user: User, permission: Permission) -> bool:
        """Check if user has a specific permission."""
        user_permissions = ROLE_PERMISSIONS.get(user.role, [])
        has_permission = permission in user_permissions

        audit_logger = get_audit_logger()
        event_type = AuditEventType.AUTHORIZATION_SUCCESS if has_permission else AuditEventType.AUTHORIZATION_FAILURE
        audit_logger.log_event(
            event_type,
            user_id=user.id,
            resource="permission",
            action="check",
            status="success" if has_permission else "failure",
            details={"permission": permission.value, "user_role": user.role.value, "has_permission": has_permission}
        )

        return has_permission

    def create_jwt_token(self, user: User, expires_delta: Optional[timedelta] = None) -> str:
        """Create JWT token for user."""
        if expires_delta is None:
            expires_delta = timedelta(hours=DEFAULT_JWT_EXPIRATION_HOURS)

        expire = datetime.utcnow() + expires_delta
        to_encode = {
            "sub": user.id,
            "username": user.username,
            "role": user.role.value,
            "exp": expire,
            "iat": datetime.utcnow(),
        }

        encoded_jwt = jwt.encode(to_encode, self._jwt_secret, algorithm="HS256")
        return encoded_jwt

    def validate_jwt_token(self, token: str) -> Optional[User]:
        """Validate JWT token and return user."""
        try:
            payload = jwt.decode(token, self._jwt_secret, algorithms=["HS256"])
            user_id: str = payload.get("sub")
            if user_id is None:
                audit_logger = get_audit_logger()
                audit_logger.log_event(
                    AuditEventType.AUTHENTICATION_FAILURE,
                    resource="jwt_token",
                    action="validate",
                    status="failure",
                    details={"reason": "missing_user_id"}
                )
                return None

            user = self.get_user(user_id)
            if user is None or not user.is_active:
                audit_logger = get_audit_logger()
                audit_logger.log_event(
                    AuditEventType.AUTHENTICATION_FAILURE,
                    resource="jwt_token",
                    action="validate",
                    status="failure",
                    details={"reason": "user_not_found_or_inactive", "user_id": user_id}
                )
                return None

            self.update_user_last_login(user.id)

            audit_logger = get_audit_logger()
            audit_logger.log_event(
                AuditEventType.AUTHENTICATION_SUCCESS,
                user_id=user.id,
                resource="jwt_token",
                action="validate",
                details={"username": user.username}
            )
            return user

        except JWTError as e:
            audit_logger = get_audit_logger()
            audit_logger.log_event(
                AuditEventType.AUTHENTICATION_FAILURE,
                resource="jwt_token",
                action="validate",
                status="failure",
                details={"reason": "jwt_decode_error", "error": str(e)}
            )
            return None

    def get_user_rate_limit(self, user_id: str) -> Optional[int]:
        """Get rate limit for user (from their API keys)."""
        user_keys = [k for k in self.api_keys.values() if k.user_id == user_id and k.is_active]
        if user_keys:
            limits = [k.rate_limit for k in user_keys if k.rate_limit is not None]
            return min(limits) if limits else None
        return None


# Global auth manager instance
_auth_manager = None

def get_auth_manager() -> APIKeyManager:
    """Get global auth manager instance."""
    global _auth_manager
    if _auth_manager is None:
        _auth_manager = APIKeyManager()
    return _auth_manager


# FastAPI Dependencies
def get_current_user(credentials: HTTPAuthorizationCredentials = Security(security)) -> User:
    """FastAPI dependency to get current authenticated user."""
    auth_manager = get_auth_manager()

    # Try API key first
    user_key = auth_manager.validate_api_key(credentials.credentials)
    if user_key:
        return user_key[0]

    # Try JWT token
    user = auth_manager.validate_jwt_token(credentials.credentials)
    if user:
        return user

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid authentication credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


def require_permission(permission: Permission):
    """Create dependency for requiring specific permission."""
    def permission_checker(current_user: User = Depends(get_current_user)) -> User:
        auth_manager = get_auth_manager()
        if not auth_manager.check_permission(current_user, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions: {permission.value} required"
            )
        return current_user
    return permission_checker


# Convenience dependencies for common roles
require_admin = require_permission(Permission.MANAGE_USERS)
require_operator = require_permission(Permission.SUBMIT_TELEMETRY)
require_phase_update = require_permission(Permission.UPDATE_PHASE)
require_analyst = require_permission(Permission.READ_STATUS)


# Pydantic models for API
class UserCreateRequest(BaseModel):
    """Request to create a new user."""
    username: str = Field(..., min_length=3, max_length=50)
    email: str = Field(..., pattern=r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
    role: UserRole
    password: Optional[str] = Field(None, min_length=8)


class UserResponse(BaseModel):
    """User information response."""
    id: str
    username: str
    email: str
    role: UserRole
    created_at: datetime
    last_login: Optional[datetime]
    is_active: bool


class APIKeyCreateRequest(BaseModel):
    """Request to create a new API key."""
    name: str = Field(..., min_length=1, max_length=100)
    permissions: Set[str] = Field(default_factory=lambda: {"read", "write"})


class APIKeyResponse(BaseModel):
    """API key information response."""
    id: str
    name: str
    permissions: Set[str]
    created_at: datetime
    expires_at: Optional[datetime]
    last_used: Optional[datetime]


class APIKeyCreateResponse(BaseModel):
    """Response after creating an API key."""
    id: str
    name: str
    key: str
    permissions: Set[str]
    created_at: datetime
    expires_at: Optional[datetime]


class LoginRequest(BaseModel):
    """User login request."""
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)


class TokenResponse(BaseModel):
    """JWT token response."""
    access_token: str
    token_type: str = "bearer"


# Global API key manager instance
_api_key_manager = None

def get_api_key_manager() -> APIKeyManager:
    """Get the global API key manager instance."""
    global _api_key_manager
    if _api_key_manager is None:
        _api_key_manager = APIKeyManager()
    return _api_key_manager


# Initialize API keys from environment variable (optional)
def initialize_from_env():
    """Initialize API keys from environment variables."""
    api_keys_env = get_secret("api_keys")
    if api_keys_env:
        try:
            key_manager = get_api_key_manager()
            for key_pair in api_keys_env.split(","):
                if ":" in key_pair:
                    name, key_value = key_pair.split(":", 1)
                    name = name.strip()
                    key_value = key_value.strip()

                    if key_value not in key_manager.api_keys:
                        key = APIKey(
                            key=key_value,
                            name=name,
                            created_at=datetime.now(),
                            permissions={"read", "write"},
                            metadata={"source": "environment"}
                        )
                        key_manager.api_keys[key_value] = key
                        key_manager.key_hashes[hashlib.sha256(key_value.encode()).hexdigest()] = key_value

            key_manager._save_keys()
            logger.info("Initialized API keys from environment")

        except Exception as e:
            logger.error(f"Failed to initialize API keys from environment: {e}")


# Initialize on module load
initialize_from_env()
