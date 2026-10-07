import logging

import httpx
from fastmcp.server.auth import AccessToken
from fastmcp.server.dependencies import get_access_token

from src.blue_button.config import API_BASE

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def call_api(token: str, endpoint: str) -> dict:
    """Make authenticated request to Blue Button FHIR API."""
    url = f"{API_BASE}/{endpoint}"
    logger.debug("Making request to Blue Button FHIR API")

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(
                url,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/fhir+json",
                },
            )
            logger.debug("Blue Button FHIR response status: %s", response.status_code)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(
                "Blue Button FHIR request failed with status %s",
                e.response.status_code,
            )
            raise
        except Exception as e:
            logger.error("Blue Button FHIR request failed: %s", type(e).__name__)
            raise


def get_patient_id_from_token() -> tuple[AccessToken, str] | tuple[None, dict]:
    """Get the access token and patient ID."""
    token = get_access_token()
    logger.debug("Access token available: %s", token is not None)

    if not token:
        logger.error("No access token available")
        return None, {"error": "Not authenticated"}

    patient_id = token.claims.get("patient")
    if not patient_id:
        logger.error("No patient ID in access token claims")
        return None, {"error": "No patient ID in token"}

    return token, patient_id
