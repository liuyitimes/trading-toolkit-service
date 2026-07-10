param(
    [string]$RepositoryRoot = (Split-Path -Parent $PSScriptRoot)
)

$gitDirectory = Join-Path $RepositoryRoot ".git"
if (-not (Test-Path $gitDirectory)) {
    throw "Not a Git repository: $RepositoryRoot"
}

git -C $RepositoryRoot config core.hooksPath .githooks
Write-Host "Configured Git hooks from .githooks"
