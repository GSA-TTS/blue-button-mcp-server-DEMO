import logging

import httpx
from fastmcp.server.auth import AccessToken, TokenVerifier
from fastmcp.server.auth.oauth_proxy import OAuthProxy

logger = logging.getLogger(__name__)


class BlueButtonTokenVerifier(TokenVerifier):
    """
    Token verifier for Blue Button API.

    Blue Button returns the beneficiary's FHIR ``patient`` id in the OAuth
    *token response* (see the CMS Authorization docs), not reliably from the
    userinfo endpoint -- the ``/Patient`` and ``/userinfo`` endpoints can be
    blocked entirely if the enrollee declines to share demographics. The
    patient id is therefore threaded in from the token exchange by
    :class:`BlueButtonOAuthProxy` (via ``extra_claims``), and this verifier
    only performs a lightweight, *non-fatal* liveness check against userinfo.
    """

    def __init__(self, api_base: str, base_url: str | None = None):
        super().__init__(base_url=base_url)
        self.api_base = api_base

    async def verify_token(self, token: str) -> AccessToken | None:
        """
        Validate the access token and return an AccessToken with claims.

        Liveness is confirmed against the userinfo endpoint when available,
        but a userinfo failure is NOT fatal: the token was already validated
        during the OAuth exchange by the proxy, and the authoritative patient
        id comes from the token response, not userinfo.
        """
        claims: dict = {}
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{self.api_base}/connect/userinfo",
                    headers={"Authorization": f"Bearer {token}"},
                )
                response.raise_for_status()
                claims = response.json()
            logger.info("userinfo claims received: keys=%s", list(claims.keys()))
        except httpx.HTTPStatusError as e:
            # Non-fatal: enrollee may have blocked demographics, or userinfo
            # may be unavailable. Fall back to token-response claims.
            logger.warning(
                "userinfo returned %s (continuing with token-response claims): %s",
                e.response.status_code,
                e.response.text,
            )
        except Exception as e:
            logger.warning(
                "userinfo request failed (%s: %s); continuing with token-response claims",
                type(e).__name__,
                e,
            )

        # Prefer an explicit patient claim (from userinfo) but the proxy will
        # inject the token-response patient id via extra_claims when missing.
        patient_id = self._extract_patient_id(claims)
        if patient_id:
            claims["patient"] = patient_id

        scopes = self._extract_scopes(claims)

        return AccessToken(
            token=token,
            client_id=claims.get("sub", "unknown"),
            scopes=scopes,
            expires_at=None,
            claims=claims,
        )

    def _extract_patient_id(self, claims: dict) -> str | None:
        """Extract patient ID from various possible claim formats."""
        # Direct patient claim (token response or userinfo)
        if claims.get("patient"):
            return claims["patient"]

        # fhir_user claim (format: "Patient/{id}" or full URL)
        fhir_user = claims.get("fhir_user")
        if fhir_user and "Patient/" in fhir_user:
            patient_id = fhir_user.split("Patient/")[-1]
            return patient_id.split("/")[0].split("?")[0]

        # sub claim as fallback
        sub = claims.get("sub")
        if isinstance(sub, str) and sub.startswith("Patient/"):
            return sub.split("Patient/")[-1]

        return None

    def _extract_scopes(self, claims: dict) -> list[str]:
        """Extract scopes from claims."""
        scope = claims.get("scope")
        if scope is None:
            return []
        if isinstance(scope, str):
            return scope.split()
        if isinstance(scope, list):
            return scope
        return []


# Keys copied from the Blue Button token response into the AccessToken claims
# so downstream tools can read them via get_access_token().claims.
_TOKEN_RESPONSE_CLAIM_KEYS = ("patient", "scope", "access_grant_expiration")


class BlueButtonOAuthProxy(OAuthProxy):
    """
    OAuthProxy specialized for CMS Blue Button.

    Blue Button returns the beneficiary ``patient`` id (and other useful
    fields) in the OAuth token response, but the base OAuthProxy only hands
    the access-token *string* to the TokenVerifier -- the token-response body
    is otherwise inaccessible to tools. This subclass overrides
    ``load_access_token`` to merge the stored token-response fields into the
    validated AccessToken's claims, making the patient id available to tools.
    """

    async def load_access_token(self, token: str) -> AccessToken | None:  # type: ignore[override]
        access_token = await super().load_access_token(token)
        if access_token is None:
            return access_token

        try:
            payload = self.jwt_issuer.verify_token(token)
            jti = payload["jti"]
            jti_mapping = await self._jti_mapping_store.get(key=jti)
            if not jti_mapping:
                return access_token
            upstream = await self._upstream_token_store.get(
                key=jti_mapping.upstream_token_id
            )
            if not upstream:
                return access_token

            raw = upstream.raw_token_data or {}
            merged = dict(access_token.claims or {})
            for key in _TOKEN_RESPONSE_CLAIM_KEYS:
                value = raw.get(key)
                # Do not overwrite a value already present from userinfo.
                if value and not merged.get(key):
                    merged[key] = value

            if merged.get("patient") and not (access_token.claims or {}).get("patient"):
                logger.info(
                    "Injected patient id from token response into access token claims"
                )

            access_token.claims = merged
        except Exception as e:
            logger.warning(
                "Could not merge token-response claims (%s: %s); "
                "proceeding with verifier claims only",
                type(e).__name__,
                e,
            )

        return access_token


def create_oauth_provider(
    client_id: str,
    client_secret: str,
    base_url: str,
    api_base: str,
) -> OAuthProxy:
    """
    Create an OAuth provider for CMS Blue Button API.

    Blue Button requires manual app registration (no DCR support),
    so we use OAuthProxy to bridge between MCP's DCR expectations
    and Blue Button's fixed OAuth flow. PKCE (S256) is required by Blue
    Button and is forwarded upstream by default (forward_pkce=True).
    """
    token_verifier = BlueButtonTokenVerifier(api_base=api_base, base_url=base_url)

    return BlueButtonOAuthProxy(
        upstream_client_id=client_id,
        upstream_client_secret=client_secret,
        upstream_authorization_endpoint=f"{api_base}/o/authorize/",
        upstream_token_endpoint=f"{api_base}/o/token/",
        token_verifier=token_verifier,
        base_url=base_url,
        valid_scopes=[
            "openid",
            "profile",
            "patient/Patient.rs",
            "patient/Coverage.rs",
            "patient/ExplanationOfBenefit.rs",
        ],
    )
