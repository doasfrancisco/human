$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

$Downloads = if ($env:HUMAN_DOWNLOADS) { $env:HUMAN_DOWNLOADS } else { "https://downloads.doashuman.com" }
$HumanHome = if ($env:HUMAN_HOME) { $env:HUMAN_HOME } else { Join-Path $env:USERPROFILE ".human" }
$Bin = Join-Path $env:USERPROFILE ".local\bin"

if (-not [Environment]::Is64BitOperatingSystem) { throw "human: 32-bit windows is not supported" }
$Place = "win32-x64"

$Version = (Invoke-RestMethod "$Downloads/latest").ToString().Trim()
$Manifest = Invoke-RestMethod "$Downloads/$Version/manifest.json"
$Item = $Manifest.platforms.$Place
if (-not $Item) { throw "human: no program for $Place in human $Version" }

$Tmp = Join-Path ([IO.Path]::GetTempPath()) ("human-" + [guid]::NewGuid())
New-Item -ItemType Directory -Path $Tmp | Out-Null
try {
    Write-Host "downloading human $Version for $Place"
    $File = Join-Path $Tmp $Item.file
    Invoke-WebRequest "$Downloads/$Version/$($Item.file)" -OutFile $File
    $Actual = (Get-FileHash $File -Algorithm SHA256).Hash.ToLower()
    if ($Actual -ne $Item.checksum) { throw "human: the checksum of $($Item.file) does not match; nothing was installed" }

    $Dest = Join-Path $HumanHome "versions\$Version"
    New-Item -ItemType Directory -Force -Path $Dest | Out-Null
    Copy-Item $File (Join-Path $Dest "human.exe") -Force

    New-Item -ItemType Directory -Force -Path $Bin | Out-Null
    $Exe = Join-Path $Bin "human.exe"
    $Old = Join-Path $Bin "human.exe.old"
    if (Test-Path $Old) { Remove-Item $Old -Force }
    if (Test-Path $Exe) { Rename-Item $Exe "human.exe.old" }
    Copy-Item (Join-Path $Dest "human.exe") $Exe
} finally {
    Remove-Item $Tmp -Recurse -Force -ErrorAction SilentlyContinue
}

& $Exe skills

$UserPath = [Environment]::GetEnvironmentVariable("Path", "User")
if (($UserPath -split ";") -notcontains $Bin) {
    [Environment]::SetEnvironmentVariable("Path", "$Bin;$UserPath", "User")
    $env:Path = "$Bin;$env:Path"
    Write-Host "added $Bin to your PATH; open a new terminal to use human"
}
Write-Host "human $Version installed at $Exe"
