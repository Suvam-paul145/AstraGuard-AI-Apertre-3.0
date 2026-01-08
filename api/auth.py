"""
API Authentication Module

Provides token-based authentication (API keys) for AstraGuard API endpoints.
Supports multiple API keys with different permissions and rate limiting.
"""

import os
import secrets
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set
from fastapi import HTTPException, status, Request, Depends
from fastapi.security import APIKeyHeader
from pydantic import BaseModel
import json
import logging

logger = logging.getLogger(__name__)


class APIKey(BaseModel):
    """API Key model with permissions and metadata."""
    key: str
    name: str
    created_at: datetime
    expires_at: Optional[datetime] = None
    permissions: Set[str] = {"read", "write"}  # Default permissions
    rate_limit: int = 1000  # Requests per hour
    is_active: bool = True
    metadata: Dict[str, str] = {}


class APIKeyManager:
    """
    Manages API keys for authentication and authorization.

    Features:
    - Multiple API keys with different permissions
    - Key expiration
    - Rate limiting
    - Key rotation support
    """

    def __init__(self, keys_file: str = "config/api_keys.json"):
        """
        Initialize API key manager.

        Args:
            keys_file: Path to JSON file storing API keys
        """
        self.keys_file = keys_file
        self.api_keys: Dict[str, APIKey] = {}
        self.key_hashes: Dict[str, str] = {}  # Store hashed versions for security
        self.rate_limits: Dict[str, List[datetime]] = {}  # Track request timestamps

        # Load existing keys
        self._load_keys()

        # Create default key if none exist (for development)
        if not self.api_keys:
            self._create_default_key()

    def _load_keys(self) -> None:
        """Load API keys from file."""
        if os.path.exists(self.keys_file):
            try:
                with open(self.keys_file, 'r') as f:
                    data = json.load(f)

                for key_data in data.get('keys', []):
                    # Convert string timestamps back to datetime
                    created_at = datetime.fromisoformat(key_data['created_at'])
                    expires_at = None
                    if key_data.get('expires_at'):
                        expires_at = datetime.fromisoformat(key_data['expires_at'])

                    key = APIKey(
                        key=key_data['key'],
                        name=key_data['name'],
                        created_at=created_at,
                        expires_at=expires_at,
                        permissions=set(key_data.get('permissions', ['read', 'write'])),
                        rate_limit=key_data.get('rate_limit', 1000),
                        is_active=key_data.get('is_active', True),
                        metadata=key_data.get('metadata', {})
                    )

                    self.api_keys[key.key] = key
                    self.key_hashes[hashlib.sha256(key.key.encode()).hexdigest()] = key.key

                logger.info(f"Loaded {len(self.api_keys)} API keys from {self.keys_file}")

            except Exception as e:
                logger.error(f"Failed to load API keys: {e}")
                # Create backup default key
                self._create_default_key()

    def _save_keys(self) -> None:
        """Save API keys to file."""
        try:
            os.makedirs(os.path.dirname(self.keys_file), exist_ok=True)

            data = {
                'keys': [
                    {
                        'key': key.key,
                        'name': key.name,
                        'created_at': key.created_at.isoformat(),
                        'expires_at': key.expires_at.isoformat() if key.expires_at else None,
                        'permissions': list(key.permissions),
                        'rate_limit': key.rate_limit,
                        'is_active': key.is_active,
                        'metadata': key.metadata
                    }
                    for key in self.api_keys.values()
                ]
            }

            with open(self.keys_file, 'w') as f:
                json.dump(data, f, indent=2)

            logger.info(f"Saved {len(self.api_keys)} API keys to {self.keys_file}")

        except Exception as e:
            logger.error(f"Failed to save API keys: {e}")

    def _create_default_key(self) -> None:
        """Create a default API key for development."""
        default_key = secrets.token_urlsafe(32)
        key = APIKey(
            key=default_key,
            name="default-development-key",
            created_at=datetime.now(),
            permissions={"read", "write", "admin"},
            rate_limit=10000,  # Higher limit for development
            metadata={"environment": "development", "auto_generated": "true"}
        )

        self.api_keys[default_key] = key
        self.key_hashes[hashlib.sha256(default_key.encode()).hexdigest()] = default_key
        self._save_keys()

        print("\n" + "=" * 80)
        print("🔑 DEFAULT API KEY CREATED")
        print("=" * 80)
        print("A default API key has been created for development:")
        print(f"API Key: {default_key}")
        print()
        print("⚠️  SECURITY WARNING:")
        print("This key has full access and should NOT be used in production!")
        print("Set the API_KEYS environment variable or create keys via the API.")
        print("=" * 80 + "\n")

    def create_key(self,
                   name: str,
                   permissions: Set[str] = None,
                   expires_in_days: int = None,
                   rate_limit: int = 1000,
                   metadata: Dict[str, str] = None) -> str:
        """
        Create a new API key.

        Args:
            name: Human-readable name for the key
            permissions: Set of permissions (read, write, admin)
            expires_in_days: Days until key expires
            rate_limit: Requests per hour
            metadata: Additional metadata

        Returns:
            The generated API key
        """
        if permissions is None:
            permissions = {"read", "write"}

        key_value = secrets.token_urlsafe(32)
        expires_at = None
        if expires_in_days:
            expires_at = datetime.now() + timedelta(days=expires_in_days)

        key = APIKey(
            key=key_value,
            name=name,
            created_at=datetime.now(),
            expires_at=expires_at,
            permissions=permissions,
            rate_limit=rate_limit,
            metadata=metadata or {}
        )

        self.api_keys[key_value] = key
        self.key_hashes[hashlib.sha256(key_value.encode()).hexdigest()] = key_value
        self._save_keys()

        logger.info(f"Created API key '{name}' with permissions: {permissions}")
        return key_value

    def validate_key(self, api_key: str) -> APIKey:
        """
        Validate an API key and return its details.

        Args:
            api_key: The API key to validate

        Returns:
            APIKey object if valid

        Raises:
            HTTPException: If key is invalid, expired, or inactive
        """
        if api_key not in self.api_keys:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API key"
            )

        key = self.api_keys[api_key]

        if not key.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="API key is inactive"
            )

        if key.expires_at and datetime.now() > key.expires_at:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="API key has expired"
            )

        return key

    def check_rate_limit(self, api_key: str) -> None:
        """
        Check if the API key has exceeded its rate limit.

        Args:
            api_key: The API key to check

        Raises:
            HTTPException: If rate limit exceeded
        """
        if api_key not in self.api_keys:
            return  # Invalid keys are caught elsewhere

        key = self.api_keys[api_key]
        now = datetime.now()

        # Initialize rate tracking for this key
        if api_key not in self.rate_limits:
            self.rate_limits[api_key] = []

        # Clean old timestamps (older than 1 hour)
        cutoff = now - timedelta(hours=1)
        self.rate_limits[api_key] = [
            ts for ts in self.rate_limits[api_key] if ts > cutoff
        ]

        # Check rate limit
        if len(self.rate_limits[api_key]) >= key.rate_limit:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded. Maximum {key.rate_limit} requests per hour."
            )

        # Add current request timestamp
        self.rate_limits[api_key].append(now)

    def revoke_key(self, api_key: str) -> bool:
        """
        Revoke an API key.

        Args:
            api_key: The API key to revoke

        Returns:
            True if key was revoked, False if not found
        """
        if api_key in self.api_keys:
            self.api_keys[api_key].is_active = False
            self._save_keys()
            logger.info(f"Revoked API key: {api_key}")
            return True
        return False

    def list_keys(self) -> List[Dict]:
        """
        List all API keys (without showing the actual key values).

        Returns:
            List of key metadata
        """
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


# Global API key manager instance
_api_key_manager = None

def get_api_key_manager() -> APIKeyManager:
    """Get the global API key manager instance."""
    global _api_key_manager
    if _api_key_manager is None:
        _api_key_manager = APIKeyManager()
    return _api_key_manager


# FastAPI security scheme
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

async def get_api_key(request: Request, api_key: str = Depends(api_key_header)) -> APIKey:
    """
    FastAPI dependency for API key authentication.

    Args:
        request: FastAPI request object
        api_key: API key from header

    Returns:
        APIKey object if valid

    Raises:
        HTTPException: If authentication fails
    """
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key required. Include 'X-API-Key' header."
        )

    key_manager = get_api_key_manager()

    # Validate the key
    key = key_manager.validate_key(api_key)

    # Check rate limit
    key_manager.check_rate_limit(api_key)

    return key


def require_permission(permission: str):
    """
    Create a dependency that requires a specific permission.

    Args:
        permission: The permission required (read, write, admin)

    Returns:
        FastAPI dependency function
    """
    async def permission_checker(api_key: APIKey = Depends(get_api_key)) -> APIKey:
        if permission not in api_key.permissions:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission '{permission}' required"
            )
        return api_key

    return permission_checker


# Initialize API keys from environment variable (optional)
def initialize_from_env():
    """Initialize API keys from environment variables."""
    api_keys_env = os.getenv("API_KEYS")
    if api_keys_env:
        try:
            # Expected format: name1:key1,name2:key2
            key_manager = get_api_key_manager()
            for key_pair in api_keys_env.split(","):
                if ":" in key_pair:
                    name, key_value = key_pair.split(":", 1)
                    name = name.strip()
                    key_value = key_value.strip()

                    # Check if key already exists
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