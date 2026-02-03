import httpx
from fastmcp.server.auth import AccessToken, TokenVerifier
from fastmcp.server.auth.oauth_proxy import OAuthProxy


class BlueButtonTokenVerifier(TokenVerifier):
    """
    Token verifier for Blue Button API.
    Validates tokens by calling the userinfo endpoint.
    """

    def __init__(self, api_base: str, base_url: str | None = None):
        super().__init__(base_url=base_url)
        self.api_base = api_base

    async def verify_token(self, token: str) -> AccessToken | None:
        """
        Validate the access token by making a request to Blue Button API.
        Returns AccessToken with claims about the authenticated user.
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.api_base}/connect/userinfo",
                    headers={"Authorization": f"Bearer {token}"},
                )
                response.raise_for_status()
                claims = response.json()

            # Extract patient ID from token claims
            patient_id = self._extract_patient_id(claims)
            if patient_id:
                claims["patient"] = patient_id

            # Extract scopes
            scopes = self._extract_scopes(claims)

            return AccessToken(
                token=token,
                client_id=claims.get("sub", "unknown"),
                scopes=scopes,
                expires_at=None,
                claims=claims,
            )

        except httpx.HTTPStatusError:
            return None
        except Exception:
            return None

    def _extract_patient_id(self, claims: dict) -> str | None:
        """Extract patient ID from various possible claim formats."""
        # Direct patient claim
        if "patient" in claims:
            return claims["patient"]

        # fhir_user claim (format: "Patient/{id}" or full URL)
        if "fhir_user" in claims:
            fhir_user = claims["fhir_user"]
            if "Patient/" in fhir_user:
                patient_id = fhir_user.split("Patient/")[-1]
                return patient_id.split("/")[0].split("?")[0]

        # sub claim as fallback
        if "sub" in claims and claims["sub"].startswith("Patient/"):
            return claims["sub"].split("Patient/")[-1]

        return None

    def _extract_scopes(self, claims: dict) -> list[str]:
        """Extract scopes from claims."""
        if "scope" not in claims:
            return []
        if isinstance(claims["scope"], str):
            return claims["scope"].split()
        if isinstance(claims["scope"], list):
            return claims["scope"]
        return []


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
    and Blue Button's fixed OAuth flow.
    """
    token_verifier = BlueButtonTokenVerifier(api_base=api_base, base_url=base_url)

    return OAuthProxy(
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
