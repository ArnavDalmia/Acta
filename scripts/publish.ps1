# Acta PyPI publish script
# Run from the repo root: .\scripts\publish.ps1

Set-Location (Split-Path $PSScriptRoot)

Write-Host "`n==> Installing build tools..." -ForegroundColor Cyan
pip install hatch --quiet

Write-Host "`n==> Cleaning old build artifacts..." -ForegroundColor Cyan
if (Test-Path dist) { Remove-Item dist -Recurse -Force }

Write-Host "`n==> Building package..." -ForegroundColor Cyan
hatch build

Write-Host "`n==> Built files:" -ForegroundColor Cyan
Get-ChildItem dist

Write-Host "`n==> Publishing to PyPI..." -ForegroundColor Cyan
Write-Host "You will be prompted for your PyPI token." -ForegroundColor Yellow
hatch publish

Write-Host "`n==> Done. Check: https://pypi.org/project/acta-ledger/" -ForegroundColor Green
