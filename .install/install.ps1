$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

$Downloads = if ($env:HUMAN_DOWNLOADS) { $env:HUMAN_DOWNLOADS } else { "https://downloads.doashuman.com" }
$HumanHome = if ($env:HUMAN_HOME) { $env:HUMAN_HOME } else { Join-Path $env:USERPROFILE ".human" }
$Versions = Join-Path $HumanHome "versions"
$Bin = Join-Path $HumanHome "bin"
$Current = Join-Path $HumanHome "current"
$Utf8 = New-Object System.Text.UTF8Encoding $false

if (-not [Environment]::Is64BitOperatingSystem) { throw "human: 32-bit windows is not supported" }
$Place = "win32-x64"

$Version = (Invoke-RestMethod "$Downloads/latest").ToString().Trim()
$Manifest = Invoke-RestMethod "$Downloads/$Version/manifest.json"
$Item = $Manifest.platforms.$Place
if (-not $Item) { throw "human: no program for $Place in human $Version" }

$Dest = Join-Path $Versions $Version
$Exe = Join-Path $Dest "human\human.exe"
if (Test-Path $Exe) {
    Write-Host "human $Version is already in $Dest"
} else {
    $Tmp = Join-Path ([IO.Path]::GetTempPath()) ("human-" + [guid]::NewGuid())
    $Staging = Join-Path $Versions ("$Version.staging-" + [guid]::NewGuid())
    New-Item -ItemType Directory -Path $Tmp | Out-Null
    try {
        Write-Host "downloading human $Version for $Place"
        $File = Join-Path $Tmp $Item.file
        Invoke-WebRequest "$Downloads/$Version/$($Item.file)" -OutFile $File
        $Actual = (Get-FileHash $File -Algorithm SHA256).Hash.ToLower()
        if ($Actual -ne $Item.checksum) { throw "human: the checksum of $($Item.file) does not match; nothing was installed" }

        New-Item -ItemType Directory -Force -Path $Staging | Out-Null
        Expand-Archive $File -DestinationPath $Staging
        $Said = ""
        try { $Said = (& (Join-Path $Staging "human\human.exe") --version 2>$null | Out-String).Trim() } catch { }
        if ($Said -ne "human $Version") {
            throw "human: the new human $Version does not start here (it said '$Said'); nothing was changed"
        }
        for ($i = 0; ; $i++) {
            try { Move-Item $Staging $Dest; break } catch { if ($i -ge 9) { throw } ; Start-Sleep -Seconds 1 }
        }
    } finally {
        Remove-Item $Tmp -Recurse -Force -ErrorAction SilentlyContinue
        if (Test-Path $Staging) { Remove-Item $Staging -Recurse -Force -ErrorAction SilentlyContinue }
    }
}

New-Item -ItemType Directory -Force -Path $Bin | Out-Null
[IO.File]::WriteAllText((Join-Path $Bin "human.cmd"), "@`"$Exe`" %* & call exit /b %%errorlevel%%`r`n", $Utf8)
[IO.File]::WriteAllText((Join-Path $Bin "human"), "#!/bin/sh`nexec `"$($Exe.Replace('\', '/'))`" `"`$@`"`n", $Utf8)

$UserPath = [Environment]::GetEnvironmentVariable("Path", "User")
$Keep = @(($UserPath -split ";") | Where-Object { $_ -and $_ -ne $Current -and $_ -ne $Bin })
[Environment]::SetEnvironmentVariable("Path", (@($Bin) + $Keep) -join ";", "User")
$env:Path = (@($Bin) + @(($env:Path -split ";") | Where-Object { $_ -and $_ -ne $Current -and $_ -ne $Bin })) -join ";"

foreach ($Old in @($Current, (Join-Path $HumanHome "old"))) {
    if (-not (Test-Path $Old)) { continue }
    $Users = @(Get-Process | Where-Object { $_.Path -and $_.Path.StartsWith($Old + "\", [StringComparison]::OrdinalIgnoreCase) })
    if ($Users.Count -eq 0) {
        Remove-Item $Old -Recurse -Force -ErrorAction SilentlyContinue
    }
    if (Test-Path $Old) {
        $Ids = ($Users | ForEach-Object { $_.Id }) -join ", "
        Write-Warning "human: $Old is still in use (process $Ids); stop that human and run the install again to delete it"
    }
}

& $Exe skills
Write-Host "human $Version installed at $Exe"
Write-Host "the human command is in $Bin; open a new terminal to use it"
