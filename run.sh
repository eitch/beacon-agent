#!/bin/bash -e
SCRIPT_DIR="$(cd ${0%/*} ; pwd)"
cd "${SCRIPT_DIR}"
python3 -u beacon_agent_main.py -f "${SCRIPT_DIR}/config.json"
exit 0