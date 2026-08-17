"""Configuration and constants for Blue Button MCP Server."""

import os

from dotenv import load_dotenv

load_dotenv()

# Blue Button API base URL - defaults to the v2 sandbox for development.
# v2 is FHIR R4 / CARIN-BB and is the version CMS recommends for new apps.
# Override with BLUE_BUTTON_API_BASE for production (https://api.bluebutton.cms.gov/v2).
API_BASE = os.environ.get("BLUE_BUTTON_API_BASE", "https://sandbox.bluebutton.cms.gov/v2")
