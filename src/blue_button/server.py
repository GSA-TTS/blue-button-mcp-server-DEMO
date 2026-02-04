"""
Blue Button API MCP Server with OAuth Authentication

Provides secure access to Medicare beneficiary data via Model Context Protocol.
Uses the CMS Blue Button 2.0 API (https://bluebutton.cms.gov/) to retrieve
FHIR-formatted patient, coverage, and claims data.
"""

import os

from dotenv import load_dotenv
from fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse

from src.blue_button.auth import create_oauth_provider
from src.blue_button.tools import register_tools

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

register_tools(mcp)


@mcp.custom_route("/health", methods=["GET"])
async def health_check(request: Request) -> JSONResponse:
    """Health check endpoint for monitoring and load balancers."""
    return JSONResponse({"status": "healthy", "service": "blue-button-mcp"})


app = mcp.http_app()
