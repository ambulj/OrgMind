# PowerShell Task Runner for OrgMind (Windows equivalent to Makefile)
param (
    [Parameter(Position=0)]
    [string]$Command = "help"
)

switch ($Command.ToLower()) {
    "setup" {
        Write-Host "Setting up OrgMind Monorepo packages..." -ForegroundColor Cyan
        python -m pip install -e packages/core
    }
    "dev" {
        Write-Host "Launching Legacy Streamlit Development UI..." -ForegroundColor Cyan
        python -m streamlit run apps/legacy-streamlit/streamlit_app.py --server.port 8501
    }
    "test" {
        Write-Host "Running Unit Tests & Smoke Test..." -ForegroundColor Cyan
        python -m pytest tests/
        python scripts/smoke_test.py
    }
    "lint" {
        Write-Host "Running Ruff Linter..." -ForegroundColor Cyan
        python -m ruff check packages/core apps scripts tests
    }
    "typecheck" {
        Write-Host "Running Mypy Type Checker..." -ForegroundColor Cyan
        python -m mypy packages/core
    }
    "format" {
        Write-Host "Formatting code with Ruff..." -ForegroundColor Cyan
        python -m ruff format packages/core apps scripts tests
        python -m ruff check --fix packages/core apps scripts tests
    }
    "seed" {
        Write-Host "Ingesting Base Datasets..." -ForegroundColor Cyan
        python packages/core/orgmind/ingest_structured.py
        python packages/core/orgmind/ingest_unstructured.py
    }
    "reset" {
        Write-Host "Resetting Graph to Baseline..." -ForegroundColor Cyan
        python scripts/reset_demo.py
    }
    "preflight" {
        Write-Host "Running Subsystem Preflight..." -ForegroundColor Cyan
        python scripts/preflight.py
    }
    default {
        Write-Host "OrgMind Task Runner Commands:" -ForegroundColor Yellow
        Write-Host "  ./tasks.ps1 setup     - Install packages in editable mode"
        Write-Host "  ./tasks.ps1 dev       - Run Streamlit development app"
        Write-Host "  ./tasks.ps1 test      - Run unit & smoke tests"
        Write-Host "  ./tasks.ps1 lint      - Run ruff linter"
        Write-Host "  ./tasks.ps1 typecheck - Run mypy type checker"
        Write-Host "  ./tasks.ps1 format    - Format code with ruff"
        Write-Host "  ./tasks.ps1 seed      - Ingest structured & unstructured data"
        Write-Host "  ./tasks.ps1 reset     - Reset graph to baseline"
        Write-Host "  ./tasks.ps1 preflight - Run preflight verification"
    }
}
