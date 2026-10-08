param([string]$ClientPath = '', [string]$DataHome = '')
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
if (-not $ClientPath) { $ClientPath = Join-Path $env:LOCALAPPDATA 'Programs\DeepSeek Harness\DeepSeek Harness.exe' }
if (-not (Test-Path -LiteralPath $ClientPath)) { throw 'Install the official DeepSeek Harness desktop app first, then specify its executable path.' }
$cli = Join-Path (Split-Path -Parent $ClientPath) 'resources\runtime\cli\bin\dsh.cmd'
if (-not (Test-Path -LiteralPath $cli)) { throw 'This Harness installation does not include the plugin installer.' }
if (Get-Process -Name 'DeepSeek Harness' -ErrorAction SilentlyContinue) { throw 'Please quit DeepSeek Harness completely, then retry. Your login will be retained.' }
if (-not $DataHome) { $DataHome = if ($env:DSH_HOME) { $env:DSH_HOME } else { Join-Path ([Environment]::GetFolderPath('UserProfile')) '.dsh' } }
$profileDir = Join-Path $DataHome 'profiles\desktop'
if (-not (Test-Path -LiteralPath (Join-Path $profileDir 'package.json'))) { throw 'Open DeepSeek Harness once before installing this plugin.' }
$backup = Join-Path $DataHome ('shorekeeper-pet\backups\' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
New-Item -ItemType Directory -Path $backup -Force | Out-Null
foreach ($name in @('package.json','cordis.patch.yml','cordis.yml','pnpm-lock.yaml','pnpm-workspace.yaml')) {
    $source = Join-Path $profileDir $name
    if (Test-Path -LiteralPath $source) { Copy-Item -LiteralPath $source -Destination (Join-Path $backup $name) }
}
$env:DSH_HOME = $DataHome
$archive = Join-Path $root 'integrations\deepseek\dsh-shorekeeper-pet-0.1.2.tgz'
if (-not (Test-Path -LiteralPath $archive)) { throw 'The plugin package is missing. Re-extract the complete pet bundle.' }
$manifest = Get-Content -LiteralPath (Join-Path $profileDir 'package.json') -Raw | ConvertFrom-Json
if ($manifest.dependencies -and $manifest.dependencies.PSObject.Properties.Name -contains 'dsh-shorekeeper-pet') {
    # Remove the old bundle through the supported CLI before add: an old file:
    # dependency can point at a previous portable folder that no longer exists.
    & $cli plugin --profile desktop remove dsh-shorekeeper-pet
    if ($LASTEXITCODE -ne 0) { throw "Could not remove the old plugin. Configuration backup: $backup" }
}
& $cli plugin --profile desktop add $archive
if ($LASTEXITCODE -ne 0) { throw "Plugin installation failed. Configuration backup: $backup" }
foreach ($name in @('index.js','state.js','package.json','cordis.patch.yml')) {
    $expected = Join-Path $root ('integrations\deepseek\' + $name)
    $installed = Join-Path $profileDir ('node_modules\dsh-shorekeeper-pet\' + $name)
    if (-not (Test-Path -LiteralPath $installed)) { throw 'The plugin was not installed completely.' }
    if ((Get-FileHash -LiteralPath $expected).Hash -ne (Get-FileHash -LiteralPath $installed).Hash) { throw 'Harness retained an older plugin. Please install the current release package again.' }
}
Write-Output 'Shorekeeper plugin installed. Reopen DeepSeek Harness and start the pet.'
