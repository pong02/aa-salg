# run.ps1
Write-Host "Running generateLabels.py..."
python generateLabels.py
if ($LASTEXITCODE -ne 0) {
    Write-Host "Error running generateLabels.py. Exiting..."
    Read-Host "Press any key to exit"
    exit 1
}

Write-Host "Running merge.py..."
python merge.py
if ($LASTEXITCODE -ne 0) {
    Write-Host "Error running merge.py. Exiting..."
    Read-Host "Press any key to exit"
    exit 1
}

Write-Host "All scripts executed successfully!"
Read-Host "Press any key to exit"
