"""
Authentication package initialization
"""

from app.auth.security import (
    hash_password,
    verify_password,
    create_access_token,
    decode_access_token,
    generate_api_key,
    hash_api_key,
    verify_api_key
)

from app.auth.dependencies import (
    AuthContext,
    get_auth_context,
    require_role,
    require_scope,
    RequireAuth,
    RequireAdmin,
    RequireOperator,
    RequireJobRead,
    RequireJobWrite,
    RequireTargetRead,
    RequireTargetWrite,
    RequireAdminAccess
)

__all__ = [
    "hash_password",
    "verify_password", 
    "create_access_token",
    "decode_access_token",
    "generate_api_key",
    "hash_api_key",
    "verify_api_key",
    "AuthContext",
    "get_auth_context",
    "require_role",
    "require_scope",
    "RequireAuth",
    "RequireAdmin", 
    "RequireOperator",
    "RequireJobRead",
    "RequireJobWrite",
    "RequireTargetRead",
    "RequireTargetWrite",
    "RequireAdminAccess"
]