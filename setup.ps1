Write-Host "Checking for Node.js and npm..."

if (Get-Command node -ErrorAction SilentlyContinue) {
    Write-Host "Node.js already installed: $(node --version)"
} else {
    Write-Host "Installing Node.js..."
    winget install OpenJS.NodeJS --accept-package-agreements --accept-source-agreements
}

if (Get-Command npm -ErrorAction SilentlyContinue) {
    Write-Host "npm already installed: $(npm --version)"
} else {
    Write-Host "npm not found. Refreshing environment..."
}

Write-Host "`nRefreshing environment variables..."
$env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")

Write-Host "`nVerifying installations..."
Write-Host "npm: $(npm --version)"

Write-Host "`nRunning npm install..."
npm i

Write-Host "`nDone!"