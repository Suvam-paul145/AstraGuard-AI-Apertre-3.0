"""
Comprehensive unit tests for core/auth.py - Authentication & Authorization Module
"""

import os
import json
import pytest
import secrets
import hashlib
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

from core.auth import (
    APIKeyManager,
    User,
    APIKey,
    UserRole,
    Permission,
    ROLE_PERMISSIONS,
    get_auth_manager,
    get_current_user,
    require_permission,
    require_admin,
    require_operator,
    require_analyst,
    require_phase_update,
    pwd_context,
)


@pytest.fixture
def temp_keys_file(tmp_path):
    """Create a temporary keys file for testing."""
    return str(tmp_path / "test_api_keys.json")


@pytest.fixture
def auth_manager(temp_keys_file, tmp_path):
    """Create an APIKeyManager with temporary storage."""
    # Patch USERS_FILE to use temp path
    users_file = tmp_path / "users.json"
    with patch("core.auth.USERS_FILE", users_file), \
         patch("core.auth.AUTH_DATA_DIR", tmp_path):
        manager = APIKeyManager(keys_file=temp_keys_file)
        return manager


class TestUserRole:
    """Test UserRole enum."""

    def test_admin_role(self):
        assert UserRole.ADMIN == "admin"

    def test_operator_role(self):
        assert UserRole.OPERATOR == "operator"

    def test_analyst_role(self):
        assert UserRole.ANALYST == "analyst"

    def test_invalid_role_raises(self):
        with pytest.raises(ValueError):
            UserRole("invalid")


class TestPermission:
    """Test Permission enum."""

    def test_all_permissions_defined(self):
        assert len(Permission) == 8

    def test_admin_has_all_permissions(self):
        admin_perms = ROLE_PERMISSIONS[UserRole.ADMIN]
        assert len(admin_perms) == 8

    def test_operator_permissions(self):
        op_perms = ROLE_PERMISSIONS[UserRole.OPERATOR]
        assert Permission.SUBMIT_TELEMETRY in op_perms
        assert Permission.UPDATE_PHASE in op_perms
        assert Permission.MANAGE_USERS not in op_perms

    def test_analyst_permissions(self):
        analyst_perms = ROLE_PERMISSIONS[UserRole.ANALYST]
        assert Permission.READ_STATUS in analyst_perms
        assert Permission.SUBMIT_TELEMETRY not in analyst_perms
        assert Permission.MANAGE_USERS not in analyst_perms


class TestUser:
    """Test User dataclass."""

    def test_user_creation(self):
        user = User(
            id="test-id",
            username="testuser",
            email="test@example.com",
            role=UserRole.OPERATOR,
            created_at=datetime.now(),
        )
        assert user.username == "testuser"
        assert user.role == UserRole.OPERATOR
        assert user.is_active is True
        assert user.last_login is None

    def test_user_to_dict(self):
        now = datetime.now()
        user = User(
            id="test-id",
            username="testuser",
            email="test@example.com",
            role=UserRole.ADMIN,
            created_at=now,
        )
        d = user.to_dict()
        assert d["id"] == "test-id"
        assert d["username"] == "testuser"
        assert d["created_at"] == now.isoformat()

    def test_user_from_dict(self):
        data = {
            "id": "test-id",
            "username": "testuser",
            "email": "test@example.com",
            "role": "operator",
            "created_at": "2025-01-01T00:00:00",
            "last_login": None,
            "is_active": True,
            "hashed_password": None,
        }
        user = User.from_dict(data)
        assert user.username == "testuser"
        assert user.role == UserRole.OPERATOR

    def test_user_roundtrip(self):
        user = User(
            id="roundtrip-id",
            username="roundtrip",
            email="rt@example.com",
            role=UserRole.ANALYST,
            created_at=datetime(2025, 1, 1),
            last_login=datetime(2025, 6, 15),
        )
        restored = User.from_dict(user.to_dict())
        assert restored.username == user.username
        assert restored.role == user.role
        assert restored.last_login is not None


class TestAPIKey:
    """Test APIKey dataclass."""

    def test_api_key_creation(self):
        key = APIKey(
            key="test-key-value",
            name="test-key",
            created_at=datetime.now(),
        )
        assert key.is_active is True
        assert key.rate_limit == 1000
        assert "read" in key.permissions

    def test_api_key_not_expired(self):
        key = APIKey(
            key="k",
            name="n",
            created_at=datetime.now(),
            expires_at=datetime.now() + timedelta(days=30),
        )
        assert key.is_expired() is False

    def test_api_key_expired(self):
        key = APIKey(
            key="k",
            name="n",
            created_at=datetime.now() - timedelta(days=60),
            expires_at=datetime.now() - timedelta(days=1),
        )
        assert key.is_expired() is True

    def test_api_key_no_expiration(self):
        key = APIKey(
            key="k",
            name="n",
            created_at=datetime.now(),
        )
        assert key.is_expired() is False

    def test_api_key_to_dict(self):
        key = APIKey(
            key="k",
            name="n",
            created_at=datetime.now(),
            permissions={"read", "write"},
        )
        d = key.to_dict()
        assert d["name"] == "n"
        assert "read" in d["permissions"]


class TestAPIKeyManager:
    """Test APIKeyManager class."""

    def test_initialization_creates_default_key(self, auth_manager):
        assert len(auth_manager.api_keys) > 0

    def test_create_user(self, auth_manager):
        user = auth_manager.create_user(
            username="newuser",
            email="new@example.com",
            role=UserRole.OPERATOR,
            password="securepassword123",
        )
        assert user.username == "newuser"
        assert user.role == UserRole.OPERATOR
        assert user.is_active is True
        assert user.hashed_password is not None

    def test_create_duplicate_user_raises(self, auth_manager):
        auth_manager.create_user(
            username="dupuser",
            email="dup@example.com",
            role=UserRole.ANALYST,
        )
        with pytest.raises(ValueError, match="already exists"):
            auth_manager.create_user(
                username="dupuser",
                email="dup2@example.com",
                role=UserRole.ANALYST,
            )

    def test_get_user(self, auth_manager):
        user = auth_manager.create_user(
            username="findme",
            email="find@example.com",
            role=UserRole.ADMIN,
        )
        found = auth_manager.get_user(user.id)
        assert found is not None
        assert found.username == "findme"

    def test_get_user_nonexistent(self, auth_manager):
        assert auth_manager.get_user("nonexistent-id") is None

    def test_update_last_login(self, auth_manager):
        user = auth_manager.create_user(
            username="loginuser",
            email="login@example.com",
            role=UserRole.OPERATOR,
        )
        assert user.last_login is None
        auth_manager.update_user_last_login(user.id)
        updated = auth_manager.get_user(user.id)
        assert updated.last_login is not None

    def test_authenticate_user_success(self, auth_manager):
        auth_manager.create_user(
            username="authuser",
            email="auth@example.com",
            role=UserRole.OPERATOR,
            password="validpassword123",
        )
        token = auth_manager.authenticate_user("authuser", "validpassword123")
        assert token is not None
        assert len(token) > 0

    def test_authenticate_user_wrong_password(self, auth_manager):
        from fastapi import HTTPException
        auth_manager.create_user(
            username="wrongpw",
            email="wp@example.com",
            role=UserRole.OPERATOR,
            password="correctpassword",
        )
        with pytest.raises(HTTPException) as exc_info:
            auth_manager.authenticate_user("wrongpw", "incorrectpassword")
        assert exc_info.value.status_code == 401

    def test_authenticate_user_nonexistent(self, auth_manager):
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            auth_manager.authenticate_user("ghostuser", "anypassword")
        assert exc_info.value.status_code == 401

    def test_create_api_key(self, auth_manager):
        user = auth_manager.create_user(
            username="keyowner",
            email="ko@example.com",
            role=UserRole.OPERATOR,
        )
        api_key = auth_manager.create_api_key(
            user_id=user.id,
            name="test-key",
            permissions={"read", "write"},
        )
        assert api_key.name == "test-key"
        assert api_key.user_id == user.id
        assert api_key.is_active is True
        assert api_key.key in auth_manager.api_keys

    def test_create_api_key_with_expiration(self, auth_manager):
        user = auth_manager.create_user(
            username="expuser",
            email="exp@example.com",
            role=UserRole.OPERATOR,
        )
        api_key = auth_manager.create_api_key(
            user_id=user.id,
            name="expiring-key",
            expires_in_days=30,
        )
        assert api_key.expires_at is not None
        assert api_key.is_expired() is False

    def test_validate_key_success(self, auth_manager):
        user = auth_manager.create_user(
            username="valuser",
            email="val@example.com",
            role=UserRole.OPERATOR,
        )
        api_key = auth_manager.create_api_key(
            user_id=user.id,
            name="valid-key",
        )
        validated = auth_manager.validate_key(api_key.key)
        assert validated.name == "valid-key"

    def test_validate_key_invalid(self, auth_manager):
        with pytest.raises(ValueError, match="Invalid API key"):
            auth_manager.validate_key("nonexistent-key-value")

    def test_validate_key_revoked(self, auth_manager):
        user = auth_manager.create_user(
            username="revuser",
            email="rev@example.com",
            role=UserRole.OPERATOR,
        )
        api_key = auth_manager.create_api_key(
            user_id=user.id,
            name="revoke-key",
        )
        auth_manager.revoke_api_key(api_key.id, user.id)
        with pytest.raises(ValueError, match="revoked"):
            auth_manager.validate_key(api_key.key)

    def test_validate_api_key_returns_user_and_key(self, auth_manager):
        user = auth_manager.create_user(
            username="vapiuser",
            email="vapi@example.com",
            role=UserRole.OPERATOR,
        )
        api_key = auth_manager.create_api_key(
            user_id=user.id,
            name="valid-api-key",
        )
        result = auth_manager.validate_api_key(api_key.key)
        assert result is not None
        returned_user, returned_key = result
        assert returned_user.username == "vapiuser"
        assert returned_key.name == "valid-api-key"

    def test_validate_api_key_invalid_returns_none(self, auth_manager):
        result = auth_manager.validate_api_key("totally-fake-key")
        assert result is None

    def test_revoke_api_key(self, auth_manager):
        user = auth_manager.create_user(
            username="revoker",
            email="revoker@example.com",
            role=UserRole.OPERATOR,
        )
        api_key = auth_manager.create_api_key(
            user_id=user.id,
            name="to-revoke",
        )
        auth_manager.revoke_api_key(api_key.id, user.id)
        assert api_key.is_active is False

    def test_revoke_api_key_nonexistent(self, auth_manager):
        with pytest.raises(ValueError, match="not found"):
            auth_manager.revoke_api_key("fake-id", "fake-user")

    def test_get_user_api_keys(self, auth_manager):
        user = auth_manager.create_user(
            username="multikey",
            email="multi@example.com",
            role=UserRole.OPERATOR,
        )
        auth_manager.create_api_key(user_id=user.id, name="key1")
        auth_manager.create_api_key(user_id=user.id, name="key2")
        keys = auth_manager.get_user_api_keys(user.id)
        assert len(keys) == 2

    def test_check_rate_limit(self, auth_manager):
        user = auth_manager.create_user(
            username="rateuser",
            email="rate@example.com",
            role=UserRole.OPERATOR,
        )
        api_key = auth_manager.create_api_key(
            user_id=user.id,
            name="rate-key",
            rate_limit=5,
        )
        # Should not raise for first 5 calls
        for _ in range(5):
            auth_manager.check_rate_limit(api_key.key)

        # 6th call should raise
        with pytest.raises(ValueError, match="Rate limit exceeded"):
            auth_manager.check_rate_limit(api_key.key)

    def test_has_permission_true(self, auth_manager):
        user = auth_manager.create_user(
            username="permuser",
            email="perm@example.com",
            role=UserRole.OPERATOR,
        )
        api_key = auth_manager.create_api_key(
            user_id=user.id,
            name="perm-key",
            permissions={"read", "write"},
        )
        assert auth_manager.has_permission(api_key.key, "read") is True

    def test_has_permission_false(self, auth_manager):
        user = auth_manager.create_user(
            username="nopermuser",
            email="noperm@example.com",
            role=UserRole.ANALYST,
        )
        api_key = auth_manager.create_api_key(
            user_id=user.id,
            name="noperm-key",
            permissions={"read"},
        )
        assert auth_manager.has_permission(api_key.key, "admin") is False

    def test_list_keys(self, auth_manager):
        keys_list = auth_manager.list_keys()
        assert isinstance(keys_list, list)
        assert len(keys_list) > 0
        assert "name" in keys_list[0]
        assert "permissions" in keys_list[0]


class TestJWTTokens:
    """Test JWT token creation and validation."""

    def test_create_jwt_token(self, auth_manager):
        user = auth_manager.create_user(
            username="jwtuser",
            email="jwt@example.com",
            role=UserRole.ADMIN,
        )
        token = auth_manager.create_jwt_token(user)
        assert token is not None
        assert len(token) > 0

    def test_validate_jwt_token(self, auth_manager):
        user = auth_manager.create_user(
            username="jwtval",
            email="jwtval@example.com",
            role=UserRole.OPERATOR,
        )
        token = auth_manager.create_jwt_token(user)
        validated_user = auth_manager.validate_jwt_token(token)
        assert validated_user is not None
        assert validated_user.username == "jwtval"

    def test_validate_jwt_token_invalid(self, auth_manager):
        result = auth_manager.validate_jwt_token("invalid.jwt.token")
        assert result is None

    def test_validate_jwt_token_expired(self, auth_manager):
        user = auth_manager.create_user(
            username="expjwt",
            email="expjwt@example.com",
            role=UserRole.ANALYST,
        )
        # Create token that's already expired
        token = auth_manager.create_jwt_token(
            user, expires_delta=timedelta(seconds=-10)
        )
        result = auth_manager.validate_jwt_token(token)
        assert result is None

    def test_jwt_token_custom_expiration(self, auth_manager):
        user = auth_manager.create_user(
            username="customexp",
            email="cexp@example.com",
            role=UserRole.OPERATOR,
        )
        token = auth_manager.create_jwt_token(
            user, expires_delta=timedelta(hours=48)
        )
        validated = auth_manager.validate_jwt_token(token)
        assert validated is not None


class TestRBACPermissions:
    """Test role-based access control."""

    def test_admin_has_manage_users(self, auth_manager):
        user = auth_manager.create_user(
            username="adminperm",
            email="admin@example.com",
            role=UserRole.ADMIN,
        )
        assert auth_manager.check_permission(user, Permission.MANAGE_USERS) is True

    def test_operator_cannot_manage_users(self, auth_manager):
        user = auth_manager.create_user(
            username="opperm",
            email="op@example.com",
            role=UserRole.OPERATOR,
        )
        assert auth_manager.check_permission(user, Permission.MANAGE_USERS) is False

    def test_operator_can_submit_telemetry(self, auth_manager):
        user = auth_manager.create_user(
            username="optel",
            email="optel@example.com",
            role=UserRole.OPERATOR,
        )
        assert auth_manager.check_permission(user, Permission.SUBMIT_TELEMETRY) is True

    def test_analyst_read_only(self, auth_manager):
        user = auth_manager.create_user(
            username="analystro",
            email="analyst@example.com",
            role=UserRole.ANALYST,
        )
        assert auth_manager.check_permission(user, Permission.READ_STATUS) is True
        assert auth_manager.check_permission(user, Permission.READ_HISTORY) is True
        assert auth_manager.check_permission(user, Permission.READ_METRICS) is True
        assert auth_manager.check_permission(user, Permission.SUBMIT_TELEMETRY) is False
        assert auth_manager.check_permission(user, Permission.UPDATE_PHASE) is False

    def test_admin_has_all_permissions(self, auth_manager):
        user = auth_manager.create_user(
            username="alladmin",
            email="all@example.com",
            role=UserRole.ADMIN,
        )
        for perm in Permission:
            assert auth_manager.check_permission(user, perm) is True


class TestUserRateLimit:
    """Test user rate limiting."""

    def test_get_user_rate_limit(self, auth_manager):
        user = auth_manager.create_user(
            username="rluser",
            email="rl@example.com",
            role=UserRole.OPERATOR,
        )
        auth_manager.create_api_key(
            user_id=user.id,
            name="rl-key",
            rate_limit=500,
        )
        limit = auth_manager.get_user_rate_limit(user.id)
        assert limit == 500

    def test_get_user_rate_limit_no_keys(self, auth_manager):
        user = auth_manager.create_user(
            username="norluser",
            email="norl@example.com",
            role=UserRole.ANALYST,
        )
        limit = auth_manager.get_user_rate_limit(user.id)
        assert limit is None


class TestPersistence:
    """Test data persistence."""

    def test_keys_persist_to_file(self, temp_keys_file, tmp_path):
        users_file = tmp_path / "users.json"
        with patch("core.auth.USERS_FILE", users_file), \
             patch("core.auth.AUTH_DATA_DIR", tmp_path):
            manager = APIKeyManager(keys_file=temp_keys_file)
            user = manager.create_user(
                username="persistuser",
                email="persist@example.com",
                role=UserRole.OPERATOR,
            )
            manager.create_api_key(
                user_id=user.id,
                name="persist-key",
            )

        # Verify file exists and has data
        assert os.path.exists(temp_keys_file)
        with open(temp_keys_file) as f:
            data = json.load(f)
        assert len(data.get("keys", [])) > 0

    def test_users_persist_to_file(self, temp_keys_file, tmp_path):
        users_file = tmp_path / "users.json"
        with patch("core.auth.USERS_FILE", users_file), \
             patch("core.auth.AUTH_DATA_DIR", tmp_path):
            manager = APIKeyManager(keys_file=temp_keys_file)
            manager.create_user(
                username="persistu",
                email="persistu@example.com",
                role=UserRole.ADMIN,
            )

        assert users_file.exists()
        with open(users_file) as f:
            data = json.load(f)
        assert len(data.get("users", [])) > 0
