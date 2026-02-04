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
    logger.debug(f"Making request to: {url}")

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(
                url,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/fhir+json",
                },
            )
            logger.debug(f"Response status: {response.status_code}")
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error: {e.response.status_code}")
            logger.error(f"Response body: {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error: {type(e).__name__}: {e}")
            raise


def get_patient_id_from_token() -> tuple[AccessToken, str] | tuple[None, dict]:
    """Get the access token and patient ID."""
    token = get_access_token()
    logger.debug(f"Token retrieved: {token is not None}")

    if not token:
        logger.error("No access token available")
        return None, {"error": "Not authenticated"}

    logger.debug(f"Token claims: {token.claims}")

    patient_id = token.claims.get("patient")
    if not patient_id:
        logger.error(f"No patient ID in token claims: {token.claims.keys()}")
        return None, {"error": "No patient ID in token"}

    logger.debug(f"Patient ID: {patient_id}")
    return token, patient_id
