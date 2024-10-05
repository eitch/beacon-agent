#!/bin/bash -e

declare SCRIPT_DIR="$(cd ${0%/*} ; pwd)"

if ! [[ -d "${SCRIPT_DIR}/venv" ]] ; then
  python3 -m venv "${SCRIPT_DIR}/venv"
  ./venv/bin/pip install requests
fi

python3 -m compileall "${SCRIPT_DIR}/src/"
sudo "${SCRIPT_DIR}/src/beacon-agent.py" -f example_config.json

exit 0