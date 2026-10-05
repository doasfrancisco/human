$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

$Downloads = if ($env:HUMAN_DOWNLOADS) { $env:HUMAN_DOWNLOADS } else { "https://downloads.doashuman.com" }
$HumanHome = if ($env:HUMAN_HOME) { $env:HUMAN_HOME } else { Join-Path $env:USERPROFILE ".human" }
$Current = Join-Path $HumanHome "current"

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

    $Unzip = Join-Path $Tmp "unzip"
    Expand-Archive $File -DestinationPath $Unzip

    if (Test-Path $Current) {
        $Away = Join-Path $HumanHome ("old\" + [guid]::NewGuid())
        Get-ChildItem $Current -Recurse -File | ForEach-Object {
            $To = Join-Path $Away $_.FullName.Substring($Current.Length + 1)
            New-Item -ItemType Directory -Force -Path (Split-Path $To) | Out-Null
            Move-Item $_.FullName $To
        }
    }
    New-Item -ItemType Directory -Force -Path $Current | Out-Null
    Copy-Item (Join-Path $Unzip "human\*") $Current -Recurse -Force
    $Exe = Join-Path $Current "human.exe"
} finally {
    Remove-Item $Tmp -Recurse -Force -ErrorAction SilentlyContinue
}

& $Exe skills

$UserPath = [Environment]::GetEnvironmentVariable("Path", "User")
if (($UserPath -split ";") -notcontains $Current) {
    [Environment]::SetEnvironmentVariable("Path", "$Current;$UserPath", "User")
    $env:Path = "$Current;$env:Path"
    Write-Host "added $Current to your PATH; open a new terminal to use human"
}
Write-Host "human $Version installed at $Exe"
