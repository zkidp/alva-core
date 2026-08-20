$ErrorActionPreference = "Stop"

$repository = if ($env:ALVA_REPOSITORY) { $env:ALVA_REPOSITORY } else { "zkidp/alva-core" }
$version = if ($env:ALVA_VERSION) { $env:ALVA_VERSION } else { "v0.14.1-preview.1" }
$installDirectory = if ($env:ALVA_INSTALL_DIR) {
    $env:ALVA_INSTALL_DIR
} else {
    Join-Path $env:LOCALAPPDATA "Programs\Alva\bin"
}

if (-not [Environment]::Is64BitOperatingSystem -or $env:PROCESSOR_ARCHITECTURE -notin @("AMD64", "x86_64")) {
    throw "This preview provides a Windows x64 binary only."
}

$asset = "alva-$version-windows-x86_64.zip"
$baseUrl = if ($env:ALVA_RELEASE_BASE_URL) {
    $env:ALVA_RELEASE_BASE_URL
} else {
    "https://github.com/$repository/releases/download/$version"
}
$temporary = Join-Path ([System.IO.Path]::GetTempPath()) ("alva-install-" + [guid]::NewGuid())

try {
    New-Item -ItemType Directory -Path $temporary | Out-Null
    $archive = Join-Path $temporary $asset
    $checksums = Join-Path $temporary "SHA256SUMS.txt"
    Invoke-WebRequest "$baseUrl/$asset" -OutFile $archive
    Invoke-WebRequest "$baseUrl/SHA256SUMS.txt" -OutFile $checksums

    $entry = Get-Content -LiteralPath $checksums |
        Where-Object { $_ -match "\s(?:\./)?$([regex]::Escape($asset))$" } |
        Select-Object -First 1
    if (-not $entry) {
        throw "Checksum entry not found for $asset."
    }
    $expected = ($entry -split "\s+")[0].ToUpperInvariant()
    $actual = (Get-FileHash -Algorithm SHA256 -LiteralPath $archive).Hash
    if ($actual -ne $expected) {
        throw "Checksum verification failed for $asset."
    }

    Expand-Archive -LiteralPath $archive -DestinationPath $temporary
    $source = Join-Path $temporary "alva-$version-windows-x86_64\alva.exe"
    New-Item -ItemType Directory -Force -Path $installDirectory | Out-Null
    Copy-Item -LiteralPath $source -Destination (Join-Path $installDirectory "alva.exe") -Force

    if (-not $env:ALVA_NO_PATH_UPDATE) {
        $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
        $pathEntries = @($userPath -split ";" | Where-Object { $_ })
        if ($installDirectory -notin $pathEntries) {
            $newPath = (@($pathEntries) + $installDirectory) -join ";"
            [Environment]::SetEnvironmentVariable("Path", $newPath, "User")
        }
        if ($installDirectory -notin @($env:Path -split ";")) {
            $env:Path = "$installDirectory;$env:Path"
        }
    }

    Write-Output "Installed alva $version to $installDirectory\alva.exe"
    & (Join-Path $installDirectory "alva.exe") --version
} finally {
    if (Test-Path -LiteralPath $temporary) {
        Remove-Item -LiteralPath $temporary -Recurse -Force
    }
}
