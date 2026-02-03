import httpx
from fastmcp.server.auth import AccessToken
from fastmcp.server.dependencies import get_access_token

from src.blue_button.server import API_BASE


async def call_api(token: str, endpoint: str) -> dict:
    """Make authenticated request to Blue Button FHIR API."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            f"{API_BASE}/{endpoint}",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/fhir+json",
            },
        )
        response.raise_for_status()
        return response.json()


def get_patient_id_from_token() -> tuple[AccessToken, str] | tuple[None, dict]:
    """
    Get the access token and patient ID.
    Returns (token, patient_id) on success, or (None, error_dict) on failure.
    """
    token = get_access_token()
    if not token:
        return None, {"error": "Not authenticated"}

    patient_id = token.claims.get("patient")
    if not patient_id:
        return None, {"error": "No patient ID in token"}

    return token, patient_id
