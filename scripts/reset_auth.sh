#!/usr/bin/env bash
#
# reset_auth.sh — reset the Blue Button OAuth flow so it can be demoed again.
#
# Re-authenticating from scratch requires clearing state at TWO server-side
# layers (a client-side layer in your MCP client, e.g. Goose, must be cleared
# separately — see the note printed at the end):
#
#   1. FastMCP OAuthProxy on-disk store — the encrypted registered client,
#      JTI mappings, and cached upstream Blue Button tokens. Survives server
#      restarts, which is why "stop and start the server" alone does nothing.
#
#   2. The CMS sandbox "Data Access Grant" for the synthetic beneficiary —
#      persists at CMS for ~1 hour. While it is live, /authorize skips the
#      consent screen. CMS exposes /o/expire_authenticated_user/ in the
#      sandbox specifically to expire it on demand.
#
# Usage:
#   ./scripts/reset_auth.sh [PATIENT_ID]
#
#   PATIENT_ID  Synthetic beneficiary id whose grant should be expired.
#               Defaults to $BLUE_BUTTON_PATIENT_ID, then to the common CMS
#               sample id -20140000000001.
#
# Environment (loaded from .env if present):
#   BLUE_BUTTON_CLIENT_ID       (required for the CMS grant-expiry step)
#   BLUE_BUTTON_CLIENT_SECRET   (required for the CMS grant-expiry step)
#   BLUE_BUTTON_API_BASE        (default: https://sandbox.bluebutton.cms.gov/v2)
#   BLUE_BUTTON_PATIENT_ID      (optional default patient id)
#
# This script only clears state — stop the server before running it and
# restart afterwards. It never touches production (guarded below).

set -euo pipefail

# Resolve repo root (parent of this script's directory) so it works from anywhere.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# --- Load .env (KEY=VALUE lines) without clobbering already-set env vars ------
ENV_FILE="${REPO_ROOT}/.env"
if [[ -f "${ENV_FILE}" ]]; then
  # shellcheck disable=SC2046
  while IFS='=' read -r key value; do
    # skip blanks and comments
    [[ -z "${key}" || "${key}" =~ ^[[:space:]]*# ]] && continue
    key="$(echo "${key}" | xargs)"          # trim whitespace
    # strip surrounding quotes from value
    value="${value%\"}"; value="${value#\"}"
    value="${value%\'}"; value="${value#\'}"
    if [[ -z "${!key:-}" ]]; then
      export "${key}=${value}"
    fi
  done < "${ENV_FILE}"
fi

API_BASE="${BLUE_BUTTON_API_BASE:-https://sandbox.bluebutton.cms.gov/v2}"
PATIENT_ID="${1:-${BLUE_BUTTON_PATIENT_ID:--20140000000001}}"

# --- Safety guard: never run the CMS expiry against production ----------------
if [[ "${API_BASE}" != *sandbox.bluebutton.cms.gov* ]]; then
  echo "REFUSING: BLUE_BUTTON_API_BASE (${API_BASE}) is not the CMS sandbox." >&2
  echo "expire_authenticated_user is a sandbox-only testing endpoint." >&2
  exit 1
fi

echo "== Blue Button auth reset =="
echo "   API base : ${API_BASE}"
echo "   Patient  : ${PATIENT_ID}"
echo

# --- Step 1: wipe the FastMCP OAuthProxy on-disk store ------------------------
# Ask FastMCP itself where its home dir is (portable across OSes) and fall back
# to a couple of well-known locations if that import is unavailable.
PYTHON_BIN="${REPO_ROOT}/.venv/bin/python"
[[ -x "${PYTHON_BIN}" ]] || PYTHON_BIN="python3"

OAUTH_DIR="$(
  "${PYTHON_BIN}" - <<'PY' 2>/dev/null || true
from fastmcp import settings
print(settings.home / "oauth-proxy")
PY
)"

if [[ -n "${OAUTH_DIR}" && -d "${OAUTH_DIR}" ]]; then
  rm -rf "${OAUTH_DIR}"
  echo "[1/2] Removed FastMCP OAuth store: ${OAUTH_DIR}"
else
  # Fallbacks for common locations if we couldn't resolve or it's absent.
  removed=0
  for candidate in \
    "${HOME}/.local/share/fastmcp/oauth-proxy" \
    "${HOME}/Library/Application Support/fastmcp/oauth-proxy" \
    "${HOME}/.fastmcp/oauth-proxy"; do
    if [[ -d "${candidate}" ]]; then
      rm -rf "${candidate}"
      echo "[1/2] Removed FastMCP OAuth store: ${candidate}"
      removed=1
    fi
  done
  [[ "${removed}" -eq 0 ]] && echo "[1/2] No FastMCP OAuth store found (already clean)."
fi

# --- Step 2: expire the CMS sandbox data access grant -------------------------
if [[ -z "${BLUE_BUTTON_CLIENT_ID:-}" || -z "${BLUE_BUTTON_CLIENT_SECRET:-}" ]]; then
  echo "[2/2] SKIPPED: BLUE_BUTTON_CLIENT_ID / BLUE_BUTTON_CLIENT_SECRET not set." >&2
  echo "       Set them (or put them in .env) to expire the CMS grant." >&2
else
  http_code="$(
    curl -sS -o /dev/null -w '%{http_code}' \
      -X POST "${API_BASE}/o/expire_authenticated_user/${PATIENT_ID}/" \
      -u "${BLUE_BUTTON_CLIENT_ID}:${BLUE_BUTTON_CLIENT_SECRET}" \
      -H "Content-Length: 0" || true
  )"
  case "${http_code}" in
    200) echo "[2/2] CMS grant expired for patient ${PATIENT_ID} (HTTP 200)." ;;
    404) echo "[2/2] No active grant for patient ${PATIENT_ID} (HTTP 404) — nothing to expire." ;;
    403) echo "[2/2] HTTP 403 FORBIDDEN — check client credentials/permissions." >&2 ;;
    *)   echo "[2/2] Unexpected response from CMS: HTTP ${http_code}." >&2 ;;
  esac
fi

echo
echo "Server-side state cleared. To fully re-run the flow:"
echo "  * In your MCP client (Goose), remove/re-add the Blue Button extension"
echo "    to drop its saved token (this script cannot reach client-side state)."
echo "  * Reconnect from an incognito/private browser window if the CMS login"
echo "    screen is skipped (clears the sandbox session cookie)."
echo "  * Restart the server:  PYTHONPATH=. PORT=8000 .venv/bin/python -m src.blue_button.server"
