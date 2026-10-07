# Blue Button MCP Server

A FastMCP server for accessing Medicare beneficiary data via the [CMS Blue Button 2.0 API](https://bluebutton.cms.gov/). Provides secure FHIR-formatted access to patient demographics, coverage, and claims data through Model Context Protocol.

## Prerequisites

- Python 3.11+
- Blue Button API OAuth credentials (sandbox or production)
- Cloud.gov account (for deployment) or local development environment

## Setup

### 1. Register for Blue Button API Access

**Sandbox (for development):**
1. Go to https://sandbox.bluebutton.cms.gov/v1/accounts/create
2. Create a developer account
3. Register a new application with:
   - **Redirect URI**: `http://localhost:8000/auth/callback` (or `<BASE_URL>/auth/callback` for your deployed URL)
   - **Client Type**: Confidential, **Grant Type**: Authorization code (PKCE/S256 required)
   - **Scopes**: Select the FHIR scopes (`patient/Patient.rs`, `patient/Coverage.rs`, `patient/ExplanationOfBenefit.rs`, plus `openid`, `profile`)
4. Note your Client ID and Client Secret

**Production (requires CMS approval):**
1. Complete sandbox testing
2. Apply for production access at https://bluebutton.cms.gov/developers/

### 2. Install Dependencies

```bash
cd blue-button-mcp-server

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -e .
```

### 3. Configure Environment

Create a `.env` file with your Blue Button credentials:

```bash
BLUE_BUTTON_CLIENT_ID=your_client_id
BLUE_BUTTON_CLIENT_SECRET=your_client_secret
BASE_URL=http://localhost:8000
USE_SANDBOX=true
```

### 4. Run the Server

FastMCP serves its own ASGI app (there is no module-level `app` object to
point uvicorn at). Run the server module directly — when `PORT` is set it
starts the HTTP transport at `/mcp`, otherwise it falls back to stdio:

```bash
# HTTP transport (for MCP clients over the network / the MCP Inspector)
PYTHONPATH=. PORT=8000 python -m src.blue_button.server

# Or with taskipy
task dev
```

The MCP endpoint will be available at `http://localhost:8000/mcp`
(health check at `http://localhost:8000/health`).

## Deployment to Cloud.gov

```bash
# Push to cloud.gov
cf push

# Set environment variables
cf set-env blue-button-mcp-server BASE_URL https://blue-button-mcp.app.cloud.gov
cf set-env blue-button-mcp-server BLUE_BUTTON_CLIENT_ID your_client_id
cf set-env blue-button-mcp-server BLUE_BUTTON_CLIENT_SECRET your_client_secret
cf restage blue-button-mcp-server
```

See `manifest.yml` for deployment configuration.

## Available Tools

| Tool | Description |
|------|-------------|
| `get_patient_info` | Get patient demographics (name, address, DOB) - requires `patient/Patient.rs` scope |
| `get_coverage_info` | Get Medicare and supplemental coverage information - requires `patient/Coverage.rs` scope |
| `get_explanation_of_benefit` | Get Medicare claim information (EOB records) - requires `patient/ExplanationOfBenefit.rs` scope |
| `search_claims` | Search claims by date range and type - filters by service date and claim type |

## Authentication

The server uses OAuth 2.0 authentication via Blue Button API. MCP clients must authenticate through the Blue Button OAuth flow, which provides:

- Tokens validated during the OAuth exchange, with a non-fatal liveness check against Blue Button's userinfo endpoint
- Automatic extraction of the beneficiary patient ID from the OAuth token response (userinfo/`/Patient` may be blocked if the enrollee declines to share demographics)
- Scope-based access control to FHIR resources

### Resetting the auth flow for repeat demos

To demo the login flow again, restarting the server is **not** enough — OAuth
state is cached in three places: your MCP client (e.g. Goose), the server's
on-disk FastMCP OAuth store, and the CMS sandbox "data access grant" (which
persists at CMS for ~1 hour). Use the helper script to clear the two
server-side layers:

```bash
# Stop the server first (Ctrl-C), then:
./scripts/reset_auth.sh                 # default synthetic patient (-20140000000001)
./scripts/reset_auth.sh -20140000000002 # a specific synthetic patient
```

The script wipes the FastMCP OAuth store and expires the CMS grant via the
sandbox-only `expire_authenticated_user` endpoint (it refuses to run against
production). It reads credentials from `.env`. Two steps it can't automate:

- In your MCP client (Goose), remove/re-add the Blue Button extension to drop
  its saved token.
- Reconnect from an incognito/private browser window if the CMS login screen
  is skipped (this clears the sandbox session cookie).

### Testing with synthetic accounts

CMS provides 10,000 synthetic Medicare enrollee accounts (realistic-but-not-real
data, so normal privacy restrictions don't apply) for testing in both the
sandbox and production. When the OAuth flow sends you to the Medicare.gov login
screen, sign in as a synthetic user using this pattern:

- **Username:** `BBUserXXXXX` (example: `BBUser00005`)
- **Password:** `PWXXXXX!` (example: `PW00005!`)

Account ranges:

| Account | Notes |
|---------|-------|
| `BBUser00000`–`BBUser09999` | Range of Medicare demographics/ages; receive new claims on a weekly rolling basis. |
| `BBUser10000` | Special account populated with nearly every field and claim type the API supports — best for exercising all four tools. |

Notes for testing:

- **Synthetic records have _negative_ patient IDs and EOB IDs** (e.g.
  `-20140000000001`); real production records are always positive. This is why
  the reset script and examples use IDs like `-20140000000001`.
- Synthetic data mimics realistic costs/dates but is **not** a longitudinal or
  clinically consistent patient view — a single account may contain
  contradictory procedures. It's for integration testing, not clinical realism.
- Claims in the weekly rolling update are dated 1–2 weeks prior, simulating
  real claim-processing lag.

## FHIR Resources

This server exposes data from the following FHIR R4 resources:
- [Patient](https://www.hl7.org/fhir/patient.html) - Demographics and personal information
- [Coverage](https://www.hl7.org/fhir/coverage.html) - Medicare coverage details
- [ExplanationOfBenefit](https://www.hl7.org/fhir/explanationofbenefit.html) - Claims and benefit information

## Development

```bash
# Run tests
task test

# Run linter
task lint

# Format code
task format

# Build package
task build
```

## License

MIT
