"""Configuration and constants for Blue Button MCP Server."""

import os

from dotenv import load_dotenv

load_dotenv()

# Blue Button API base URL - defaults to sandbox for development
API_BASE = os.environ.get("BLUE_BUTTON_API_BASE", "https://sandbox.bluebutton.cms.gov/v2")
