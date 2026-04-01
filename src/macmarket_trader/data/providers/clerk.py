"""Clerk JWT verification boundary implementation."""

from __future__ import annotations

from typing import Any

import jwt

from macmarket_trader.data.providers.base import AuthProvider


class ClerkAuthProvider(AuthProvider):
    """Verifies bearer JWTs against Clerk issuer and JWKS endpoint."""

    def __init__(self, issuer: str, jwks_url: str, *, audience: str | None = None) -> None:
        if not issuer:
            raise ValueError("clerk_jwt_issuer is required for clerk auth provider")
        if not jwks_url:
            raise ValueError("clerk_jwks_url is required for clerk auth provider")
        self.issuer = issuer
        self.jwks_url = jwks_url
        self.audience = audience
        self._jwk_client = jwt.PyJWKClient(jwks_url)

    def verify_token(self, token: str) -> dict[str, Any]:
        signing_key = self._jwk_client.get_signing_key_from_jwt(token)
        options = {"verify_aud": self.audience is not None}
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            issuer=self.issuer,
            audience=self.audience,
            options=options,
        )
        if not isinstance(claims, dict):
            raise ValueError("Invalid Clerk claims payload")
        return claims
