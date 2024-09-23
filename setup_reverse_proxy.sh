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
ssh -fN -R ${PORT}:localhost:${PORT} ${REMOTE_USER}@${REMOTE_HOST}
echo "SSH tunnel established."

# ----------------------------- #
#      Remote Host Setup        #
# ----------------------------- #

echo "Configuring remote host and starting PM2..."

# Execute commands on the remote host using a single SSH session
ssh -tt ${REMOTE_USER}@${REMOTE_HOST} <<EOF
    set -e

    # Load the environment from .bashrc or .profile to get node/npm/pm2 paths
    source ~/.bashrc || source ~/.profile

    # Navigate to the scripts directory
    cd ${REMOTE_SCRIPTS_DIR}

    # Export environment variables for PM2
    export PORT=${PORT}
    export SECRET_PASSWORD=${PASSWORD}

    # Start the applications using the pre-existing PM2 ecosystem file
    echo "Starting applications with PM2..."
    pm2 start ${ECOSYSTEM_FILE}

    # Save the PM2 process list and ensure it resurrects on reboot
    pm2 save
    pm2 startup systemd -u ${REMOTE_USER} --hp /home/${REMOTE_USER}

    echo "PM2 has been configured and started the applications."
EOF

echo "Setup complete. Press Ctrl+C to stop the SSH tunnel."
