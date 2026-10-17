# Reset demo PowerShell wrapper
Write-Host "Triggering clean demo reset for northwind_labs..." -ForegroundColor Cyan
python "$PSScriptRoot/reset_demo.py"
python "$PSScriptRoot/smoke_test.py"
