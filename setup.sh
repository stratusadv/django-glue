#!/bin/bash

# Install npm and run npm install

echo "Checking for Node.js and npm..."

if command -v node &> /dev/null; then
    echo "Node.js already installed: $(node --version)"
else
    echo "Installing Node.js..."
    if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" || "$OSTYPE" == "win32" ]]; then
        # Windows
        winget install OpenJS.NodeJS --accept-package-agreements --accept-source-agreements
    elif command -v apt-get &> /dev/null; then
        # Debian/Ubuntu
        curl -fsSL https://deb.nodesource.com/setup_lts.x | sudo -E bash -
        sudo apt-get install -y nodejs
    elif command -v dnf &> /dev/null; then
        # Fedora
        sudo dnf install -y nodejs npm
    elif command -v yum &> /dev/null; then
        # CentOS/RHEL
        curl -fsSL https://rpm.nodesource.com/setup_lts.x | sudo bash -
        sudo yum install -y nodejs
    elif command -v brew &> /dev/null; then
        # macOS
        brew install node
    else
        echo "Could not detect package manager. Please install Node.js manually."
        exit 1
    fi
fi

if command -v npm &> /dev/null; then
    echo "npm already installed: $(npm --version)"
else
    echo "npm not found after Node.js installation. Please check your installation."
    exit 1
fi

echo -e "\nRunning npm install..."
npm i

echo -e "\nDone!"