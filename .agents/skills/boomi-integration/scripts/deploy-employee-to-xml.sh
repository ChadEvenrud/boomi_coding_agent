#!/usr/bin/env bash
# Deploy Employee Data to XML integration components in dependency order.
# Usage: bash scripts/deploy-employee-to-xml.sh [--folder-id FOLDER_ID]
# Run from the skill/project root (directory containing .env and active-development/).

set -euo pipefail

SKILL_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
source "${SKILL_ROOT}/scripts/boomi-common.sh"
load_env
require_env BOOMI_API_URL BOOMI_USERNAME BOOMI_API_TOKEN BOOMI_ACCOUNT_ID

AD="${SKILL_ROOT}/active-development"
JSON_PROFILE="${AD}/profile.json/Employee_JSON_Profile.xml"
XML_PROFILE="${AD}/profile.xml/Employee_XML_Profile.xml"
MAP="${AD}/transform.map/Employee_JSON_to_XML_Map.xml"
PROCESS="${AD}/process/Employee_Data_to_XML.xml"
FOLDER_ID=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --folder-id) FOLDER_ID="$2"; shift 2 ;;
    *) echo "Unknown option: $1" >&2; exit 1 ;;
  esac
done

[[ -z "$FOLDER_ID" ]] && FOLDER_ID="${BOOMI_TARGET_FOLDER:-}"

if [[ -z "$FOLDER_ID" || "$FOLDER_ID" == "REPLACE_WITH_FOLDER_ID" ]]; then
  echo "ERROR: Set BOOMI_TARGET_FOLDER in .env or pass --folder-id" >&2
  exit 1
fi

for file in "$JSON_PROFILE" "$XML_PROFILE" "$MAP" "$PROCESS"; do
  if grep -q 'REPLACE_WITH_FOLDER_ID' "$file"; then
    sedi "s/REPLACE_WITH_FOLDER_ID/${FOLDER_ID}/g" "$file"
  fi
done

extract_id() {
  grep -o -m 1 'componentId="[^"]*"' "$1" | sed 's/componentId="//;s/"//'
}

create_if_needed() {
  local file="$1"
  local id
  id="$(extract_id "$file")"
  if [[ -z "$id" ]]; then
    bash "${SKILL_ROOT}/scripts/boomi-component-create.sh" "$file"
  else
    echo "Skipping create (already has ID): $(basename "$file") -> ${id}"
  fi
}

cd "${SKILL_ROOT}"

create_if_needed "$JSON_PROFILE"
create_if_needed "$XML_PROFILE"

JSON_ID="$(extract_id "$JSON_PROFILE")"
XML_ID="$(extract_id "$XML_PROFILE")"

sedi "s/fromProfile=\"[^\"]*\"/fromProfile=\"${JSON_ID}\"/" "$MAP"
sedi "s/toProfile=\"[^\"]*\"/toProfile=\"${XML_ID}\"/" "$MAP"

create_if_needed "$MAP"

MAP_ID="$(extract_id "$MAP")"
sedi "s/mapId=\"[^\"]*\"/mapId=\"${MAP_ID}\"/" "$PROCESS"

create_if_needed "$PROCESS"

echo ""
echo "Deployment complete."
echo "  JSON Profile: ${JSON_ID}"
echo "  XML Profile:  ${XML_ID}"
echo "  Map:          ${MAP_ID}"
echo "  Process:      $(extract_id "$PROCESS")"
echo ""
echo "Next: bash scripts/boomi-deploy.sh active-development/process/Employee_Data_to_XML.xml"
echo "      bash scripts/boomi-test-execute.sh <process-component-id>"
