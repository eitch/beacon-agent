#!/bin/bash -e
SCRIPT_DIR="$(cd ${0%/*} ; pwd)"
"${SCRIPT_DIR}/beacon_agent_main.py" -f example_config.json
exit 0