#!/bin/bash

declare SCRIPT_DIR="$(cd ${0%/*} ; pwd)"

if ! [[ -d venv ]] ; then
  python3 -m venv venv
  ./venv/bin/pip install requests
fi

python3 -m compileall "${SCRIPT_DIR}/src/"
sudo "${SCRIPT_DIR}/src/beacon-agent.py"

exit 0