# Drama Processor - Generic Runtime Package Tool

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

$InfoColor = "Cyan"
$SuccessColor = "Green"
$ErrorColor = "Red"

Write-Host "========================================" -ForegroundColor $InfoColor
Write-Host "   Drama Processor - Generic Runtime" -ForegroundColor $InfoColor
Write-Host "========================================" -ForegroundColor $InfoColor
Write-Host ""

$outputDir = "D:\Package-Output"

try {
    & "$PSScriptRoot\package.ps1" -OutputDir $outputDir

    if ($LASTEXITCODE -ne 0) {
        throw "Packaging failed with exit code $LASTEXITCODE"
    }

    Write-Host "" 
    Write-Host "========================================" -ForegroundColor $SuccessColor
    Write-Host "   Generic Runtime Package Complete!" -ForegroundColor $SuccessColor
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
