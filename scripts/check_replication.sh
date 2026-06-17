#!/usr/bin/env bash
# check_replication.sh
# Polls US and AS endpoints until both serve the same version, then prints delay.
#
# Usage:
#   ./scripts/check_replication.sh <us_url> <as_url> [interval_seconds]
#
# Example:
#   ./scripts/check_replication.sh https://ampypay-us.onrender.com https://ampypay-as.onrender.com
#   ./scripts/check_replication.sh https://us.ampypay.com https://as.ampypay.com 30
#
# The script:
#   1. Reads the current version from US (as the "expected" version after deploy)
#   2. Records the timestamp when US first showed that version
#   3. Polls AS every INTERVAL seconds until it returns the same version
#   4. Prints the replication delay

set -euo pipefail

US_URL="${1:-}"
AS_URL="${2:-}"
INTERVAL="${3:-15}"  # seconds between polls
VERSION_PATH="/version.json"

if [[ -z "$US_URL" || -z "$AS_URL" ]]; then
  echo "Usage: $0 <us_url> <as_url> [interval_seconds]"
  echo "Example: $0 https://us.ampypay.com https://as.ampypay.com 15"
  exit 1
fi

fetch_version() {
  local url="$1${VERSION_PATH}"
  # -sf: silent + fail on HTTP error, --max-time: timeout per request
  curl -sf --max-time 10 "$url" 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('version',''))" 2>/dev/null || echo ""
}

epoch_now() {
  date +%s
}

iso_now() {
  date -u +"%Y-%m-%dT%H:%M:%SZ"
}

echo "=== Replication Delay Checker ==="
echo "US: $US_URL"
echo "AS: $AS_URL"
echo "Poll interval: ${INTERVAL}s"
echo ""

# Step 1: Get current version from US
echo "[$(iso_now)] Fetching version from US..."
US_VERSION=$(fetch_version "$US_URL")

if [[ -z "$US_VERSION" ]]; then
  echo "ERROR: Could not fetch version from US ($US_URL${VERSION_PATH})"
  echo "Make sure version.json exists and is accessible."
  exit 1
fi

echo "[$(iso_now)] US version: $US_VERSION"
US_SEEN_AT=$(epoch_now)
US_SEEN_ISO=$(iso_now)
echo "[$(iso_now)] US timestamp recorded: $US_SEEN_ISO"
echo ""
echo "Now polling AS until it returns the same version..."
echo ""

# Step 2: Poll AS until versions match
attempt=0
while true; do
  attempt=$((attempt + 1))
  AS_VERSION=$(fetch_version "$AS_URL")
  AS_CHECK_ISO=$(iso_now)

  if [[ -z "$AS_VERSION" ]]; then
    echo "[$AS_CHECK_ISO] Attempt $attempt: AS did not respond (will retry)"
  elif [[ "$AS_VERSION" == "$US_VERSION" ]]; then
    AS_SEEN_AT=$(epoch_now)
    AS_SEEN_ISO="$AS_CHECK_ISO"
    echo "[$AS_CHECK_ISO] Attempt $attempt: AS version matches! ($AS_VERSION)"
    break
  else
    echo "[$AS_CHECK_ISO] Attempt $attempt: AS version=$AS_VERSION (waiting for $US_VERSION)"
  fi

  sleep "$INTERVAL"
done

# Step 3: Calculate delay
DELAY_SECONDS=$((AS_SEEN_AT - US_SEEN_AT))
DELAY_MINUTES=$(echo "scale=2; $DELAY_SECONDS / 60" | bc)

echo ""
echo "=============================="
echo "  REPLICATION DELAY RESULT"
echo "=============================="
echo "  Version tracked : $US_VERSION"
echo "  US saw version  : $US_SEEN_ISO"
echo "  AS saw version  : $AS_SEEN_ISO"
echo "  Delay           : ${DELAY_SECONDS}s (~${DELAY_MINUTES} min)"
echo "=============================="
