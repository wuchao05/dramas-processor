# Drama Processor - Interactive Package Tool
# Pure PowerShell interactive menu for packaging

# Set encoding
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

# Set colors
$ErrorColor = "Red"
$SuccessColor = "Green"
$InfoColor = "Cyan"
$WarningColor = "Yellow"

Write-Host "========================================" -ForegroundColor $InfoColor
Write-Host "   Drama Processor - Package Tool" -ForegroundColor $InfoColor
Write-Host "========================================" -ForegroundColor $InfoColor
Write-Host ""

# Check configs/users directory
if (-not (Test-Path "configs\users")) {
    Write-Host "ERROR: configs\users\ directory not found!" -ForegroundColor $ErrorColor
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host "Scanning available user configs..." -ForegroundColor $WarningColor
Write-Host ""
Write-Host "Please select package target:" -ForegroundColor $InfoColor
Write-Host ""

# Scan YAML files and build menu
$configs = @()
$index = 1

Get-ChildItem -Path "configs\users\*.yaml" | ForEach-Object {
    $filename = $_.BaseName
    # Exclude -daily files
    if ($filename -notmatch "-daily$") {
        Write-Host "[$index] $filename" -ForegroundColor White
        $configs += $filename
        $index++
    }
}

# Check if any configs found
if ($configs.Count -eq 0) {
    Write-Host ""
    Write-Host "ERROR: No config files found in configs\users\!" -ForegroundColor $ErrorColor
    Write-Host "Please ensure .yaml files exist (e.g. xh.yaml)" -ForegroundColor $WarningColor
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host ""
Write-Host "[0] Exit" -ForegroundColor White
Write-Host ""

# Read user input
do {
    $choice = Read-Host "Enter option (0-$($configs.Count))"
    
    # Validate input
    if ($choice -eq "") {
        Write-Host "ERROR: No option entered!" -ForegroundColor $ErrorColor
        continue
    }
    
    # Check for exit
    if ($choice -eq "0") {
        Write-Host "Exiting..." -ForegroundColor $WarningColor
        exit 0
    }
    
    # Validate numeric input
    $choiceNum = 0
    if (-not [int]::TryParse($choice, [ref]$choiceNum)) {
        Write-Host "ERROR: Please enter a valid number!" -ForegroundColor $ErrorColor
        continue
    }
    
    # Validate range
    if ($choiceNum -lt 1 -or $choiceNum -gt $configs.Count) {
        Write-Host "ERROR: Please enter a number between 1 and $($configs.Count)!" -ForegroundColor $ErrorColor
        continue
    }
    
    # Valid choice
    break
    
} while ($true)

# Get selected config name
$name = $configs[$choiceNum - 1]

Write-Host ""
Write-Host "Packaging for: $name" -ForegroundColor $SuccessColor
Write-Host ""

# Set output directory
$outputDir = "D:\Package-Output"

# Call package.ps1
try {
    & "$PSScriptRoot\package.ps1" -Name $name -OutputDir $outputDir
    
    if ($LASTEXITCODE -ne 0) {
        throw "Packaging failed with exit code $LASTEXITCODE"
    }
    
    Write-Host ""
    Write-Host "========================================" -ForegroundColor $SuccessColor
    Write-Host "   Package Complete!" -ForegroundColor $SuccessColor
    Write-Host "   Config: $name" -ForegroundColor White
    Write-Host "   Output: $outputDir" -ForegroundColor White
    Write-Host "========================================" -ForegroundColor $SuccessColor
    
} catch {
    Write-Host ""
    Write-Host "========================================" -ForegroundColor $ErrorColor
    Write-Host "   Packaging Failed!" -ForegroundColor $ErrorColor
    Write-Host "========================================" -ForegroundColor $ErrorColor
    Write-Host ""
    Write-Host "Error: $_" -ForegroundColor $ErrorColor
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host ""
Read-Host "Press Enter to exit"
