#!/bin/bash

declare SCRIPT_DIR="$(cd ${0%/*} ; pwd)"

python3 -m compileall "${SCRIPT_DIR}/src/"
sudo "${SCRIPT_DIR}/src/beacon-agent.py"

exit 0