#!/bin/bash

# -------------------------------------------------------------------
# Script: setup_remote.sh
# Description: Sets up a reverse SSH tunnel and manages Python scripts
#              on a remote host using PM2.
# Usage: ./setup_remote.sh <PORT> <PASSWORD>
# -------------------------------------------------------------------

# Exit immediately if a command exits with a non-zero status
set -e

# ----------------------------- #
#        Argument Handling      #
# ----------------------------- #

if [ $# -ne 2 ]; then
    echo "Usage: $0 <PORT> <PASSWORD>"
    exit 1
fi

PORT=$1
PASSWORD=$2

# ----------------------------- #
#        Configuration          #
# ----------------------------- #

REMOTE_USER="xilinx"
REMOTE_HOST="makerslab-fpga-23.d2.comp.nus.edu.sg"
REMOTE_SCRIPTS_DIR="/home/${REMOTE_USER}/.external_comms"  # Adjust as needed
ECOSYSTEM_FILE="/home/${REMOTE_USER}/.external_comms/ecosystem.config.js"  # Assume this file already exists

# ----------------------------- #
#    Establish SSH Tunnel       #
# ----------------------------- #

# Establish SSH Tunnel and keep it open until Ctrl+C
echo "Establishing reverse SSH tunnel on port ${PORT}..."
ssh -tt -R 8000:localhost:${PORT} ${REMOTE_USER}@${REMOTE_HOST} <<EOF
	set -e

	source ~/.bashrc || source ~/.profile

	cd ${REMOTE_SCRIPTS_DIR}

	export PORT=${PORT}
	export SECRET_PASSWORD=${PASSWORD}

	echo "Starting applications with PM2..."
	pm2 start ${ECOSYSTEM_FILE}

	echo "PM2 has been configured and started the applications."
EOF

echo "SSH tunnel killed"

