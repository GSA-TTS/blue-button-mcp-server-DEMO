"""
Blue Button API MCP Server with OAuth Authentication

Provides secure access to Medicare beneficiary data via Model Context Protocol.
Uses the CMS Blue Button 2.0 API (https://bluebutton.cms.gov/) to retrieve
FHIR-formatted patient, coverage, and claims data.
"""

import os

import httpx
from dotenv import load_dotenv
from fastmcp import FastMCP
from fastmcp.server.auth import AccessToken
from fastmcp.server.context import Context
from fastmcp.server.dependencies import get_access_token
from starlette.requests import Request
from starlette.responses import JSONResponse

from auth import create_oauth_provider

load_dotenv()

# Blue Button API base URL - defaults to sandbox for development
API_BASE = os.environ.get("BLUE_BUTTON_API_BASE", "https://sandbox.bluebutton.cms.gov/v2")


def create_server() -> FastMCP:
    """Create and configure the MCP server."""
    client_id = os.environ.get("BLUE_BUTTON_CLIENT_ID")
    client_secret = os.environ.get("BLUE_BUTTON_CLIENT_SECRET")

    if not client_id or not client_secret:
        raise ValueError(
            "Missing required environment variables: "
            "BLUE_BUTTON_CLIENT_ID and BLUE_BUTTON_CLIENT_SECRET"
        )

    auth = create_oauth_provider(
        client_id=client_id,
        client_secret=client_secret,
        base_url=os.environ.get("BASE_URL", "http://localhost:8000"),
        api_base=API_BASE,
    )

    return FastMCP(name="Blue Button Medicare Data", auth=auth)


mcp = create_server()


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


@mcp.tool()
async def get_patient_info(ctx: Context) -> dict:
    """
    Get patient demographic and personal information.
    Returns FHIR Patient resource with name, address, birth date, etc.
    Requires patient/Patient.rs scope.
    """
    result = get_patient_id_from_token()
    if result[0] is None:
        return result[1]
    token, patient_id = result

    try:
        data = await call_api(token.token, f"fhir/Patient/{patient_id}")
        return {"patient_id": patient_id, "data": data}
    except httpx.HTTPStatusError as e:
        return {"error": f"API error: {e.response.status_code}", "detail": str(e)}


@mcp.tool()
async def get_coverage_info(ctx: Context) -> dict:
    """
    Get Medicare and supplemental coverage information.
    Returns FHIR Coverage resources showing insurance plans and periods.
    Requires patient/Coverage.rs scope.
    """
    result = get_patient_id_from_token()
    if result[0] is None:
        return result[1]
    token, patient_id = result

    try:
        data = await call_api(token.token, f"fhir/Coverage?beneficiary={patient_id}")
        return {"patient_id": patient_id, "coverage": data}
    except httpx.HTTPStatusError as e:
        return {"error": f"API error: {e.response.status_code}", "detail": str(e)}


@mcp.tool()
async def get_explanation_of_benefit(ctx: Context, eob_id: str | None = None) -> dict:
    """
    Get Medicare claim information (Explanation of Benefit records).
    Returns FHIR ExplanationOfBenefit resources with claim details.
    Requires patient/ExplanationOfBenefit.rs scope.

    Args:
        eob_id: Optional specific EOB ID. If not provided, returns all EOBs.
    """
    result = get_patient_id_from_token()
    if result[0] is None:
        return result[1]
    token, patient_id = result

    try:
        if eob_id:
            endpoint = f"fhir/ExplanationOfBenefit/{eob_id}"
        else:
            endpoint = f"fhir/ExplanationOfBenefit?patient={patient_id}"

        data = await call_api(token.token, endpoint)
        return {"patient_id": patient_id, "claims": data}
    except httpx.HTTPStatusError as e:
        return {"error": f"API error: {e.response.status_code}", "detail": str(e)}


@mcp.tool()
async def search_claims(
    ctx: Context,
    service_date_start: str | None = None,
    service_date_end: str | None = None,
    claim_type: str | None = None,
) -> dict:
    """
    Search for claims with filters.

    Args:
        service_date_start: Filter claims from this date (YYYY-MM-DD)
        service_date_end: Filter claims to this date (YYYY-MM-DD)
        claim_type: Type of claim (carrier, inpatient, outpatient, snf, hospice, hha, dme, pde)
    """
    result = get_patient_id_from_token()
    if result[0] is None:
        return result[1]
    token, patient_id = result

    params = [f"patient={patient_id}"]
    if service_date_start:
        params.append(f"service-date=ge{service_date_start}")
    if service_date_end:
        params.append(f"service-date=le{service_date_end}")
    if claim_type:
        params.append(f"type={claim_type}")

    try:
        data = await call_api(token.token, f"fhir/ExplanationOfBenefit?{'&'.join(params)}")
        return {
            "patient_id": patient_id,
            "filters": {
                "service_date_start": service_date_start,
                "service_date_end": service_date_end,
                "claim_type": claim_type,
            },
            "results": data,
        }
    except httpx.HTTPStatusError as e:
        return {"error": f"API error: {e.response.status_code}", "detail": str(e)}


@mcp.custom_route("/health", methods=["GET"])
async def health_check(request: Request) -> JSONResponse:
    """Health check endpoint for monitoring and load balancers."""
    return JSONResponse({"status": "healthy", "service": "blue-button-mcp"})


app = mcp.http_app()
