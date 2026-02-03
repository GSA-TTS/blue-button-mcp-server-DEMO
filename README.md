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
   - **Redirect URI**: `http://localhost:8000/callback` (or your deployed URL)
   - **Scopes**: Select required FHIR scopes (Patient, Coverage, ExplanationOfBenefit)
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

```bash
# Using uvicorn directly
uvicorn blue_button_server:app --host 0.0.0.0 --port 8000 --reload

# Or with taskipy
task dev
```

The server will be available at `http://localhost:8000`

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

- Access tokens validated against Blue Button's userinfo endpoint
- Automatic extraction of patient ID from token claims
- Scope-based access control to FHIR resources

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
