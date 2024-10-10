#!/bin/bash -e
SCRIPT_DIR="$(cd ${0%/*} ; pwd)"
cd "${SCRIPT_DIR}"

SERVICE_FILE="${SCRIPT_DIR}/systemd/beacon-agent.service"

# Define the current directory's run.sh script path
RUN_SCRIPT_PATH="${SCRIPT_DIR}/run.sh"

# Use sed to replace the ExecStart= line with the new script path
sed -i "s|^ExecStart=.*|ExecStart=${RUN_SCRIPT_PATH}|" "$SERVICE_FILE"

cp "${SERVICE_FILE}" /etc/systemd/system/beacon-agent.service
systemctl daemon-reload
sudo systemctl enable beacon-agent.service
sudo systemctl start beacon-agent.service

exit 0