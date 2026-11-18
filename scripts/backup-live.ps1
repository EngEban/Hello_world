<#
Downloads a manual backup of the live Railway site: the PostgreSQL database
(pg_dump custom format) and the uploaded-files volume (/data/media as .tar.gz).
Needs only the Railway CLI, logged in and linked to this project (railway link);
no PostgreSQL tools are required on this computer. Each file is checked against
a SHA-256 taken on the server. The files contain personal data (e-mails,
password hashes): keep them private and never commit them.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory)] [string]$Destination,
    [string]$DatabaseService = 'resref-staging-db',
    [string]$WebService = 'resref-staging-api',
    [switch]$SkipMedia
)

$ErrorActionPreference = 'Stop'
$stamp = Get-Date -Format 'yyyyMMdd-HHmm'
if (-not (Test-Path $Destination -PathType Container)) {
    throw "Destination folder does not exist: $Destination"
}

function Invoke-RailwayShell([string]$Service, [string]$Command) {
    # The CLI prints notices on stderr; Windows PowerShell would turn them into errors.
    $previous = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        $lines = & railway ssh --service $Service -- $Command 2>$null
        if ($LASTEXITCODE -ne 0) { throw "railway ssh to $Service failed (exit $LASTEXITCODE)." }
    }
    finally {
        $ErrorActionPreference = $previous
    }
    return @($lines)
}

function Save-RemoteFile([string]$Service, [string]$CreateCommand, [string]$RemotePath, [string]$LocalPath) {
    # 1. Create the file on the server and read its checksum and size.
    $created = Invoke-RailwayShell $Service "$CreateCommand && sha256sum $RemotePath && stat -c 'size=%s' $RemotePath"
    $hashLine = $created | Where-Object { $_ -match "^([0-9a-f]{64})\s+$([regex]::Escape($RemotePath))$" } | Select-Object -Last 1
    if (-not $hashLine) { throw "Could not create $RemotePath on $Service." }
    $expected = $Matches[1]
    $sizeLine = $created | Where-Object { $_ -match '^size=(\d+)$' } | Select-Object -Last 1
    if (-not $sizeLine) { throw "Could not read the size of $RemotePath on $Service." }
    $total = [long]$Matches[1]
    # 2. Download it as base64 text in 20 MB chunks (one large stream fails over railway ssh),
    #    then remove the server copy.
    $chunk = 20MB
    $stream = [IO.File]::Create($LocalPath)
    try {
        for ($offset = 0L; $offset -lt $total; $offset += $chunk) {
            if ($total -gt $chunk) {
                Write-Host ('  downloading {0:N0} of {1:N0} MB...' -f [math]::Min(($offset + $chunk) / 1MB, $total / 1MB), ($total / 1MB))
            }
            $encoded = Invoke-RailwayShell $Service "tail -c +$($offset + 1) $RemotePath | head -c $chunk | base64 -w0; echo"
            $payload = $encoded | Where-Object { $_ -match '^[A-Za-z0-9+/]+=*$' } | Sort-Object Length -Descending | Select-Object -First 1
            if (-not $payload) { throw "Download of $RemotePath from $Service failed." }
            $bytes = [Convert]::FromBase64String($payload)
            $stream.Write($bytes, 0, $bytes.Length)
        }
    }
    finally {
        $stream.Dispose()
        Invoke-RailwayShell $Service "rm -f $RemotePath" | Out-Null
    }
    $actual = (Get-FileHash -Algorithm SHA256 $LocalPath).Hash.ToLowerInvariant()
    if ($actual -ne $expected) {
        Remove-Item $LocalPath
        throw "Checksum mismatch for $LocalPath; the file was removed. Run the backup again."
    }
    $size = '{0:N1} MB' -f ((Get-Item $LocalPath).Length / 1MB)
    Write-Host "  saved $LocalPath ($size, checksum OK)" -ForegroundColor Green
}

Write-Host 'Backing up the live database...'
Save-RemoteFile $DatabaseService `
    'pg_dump -U "$PGUSER" -d "$PGDATABASE" -Fc --no-owner --no-privileges -f /tmp/resref-backup.dump' `
    '/tmp/resref-backup.dump' (Join-Path $Destination "railway-live-db-$stamp.dump")

if (-not $SkipMedia) {
    Write-Host 'Backing up uploaded files (/data/media)...'
    Save-RemoteFile $WebService `
        'tar -C /data -czf /tmp/resref-media.tar.gz media' `
        '/tmp/resref-media.tar.gz' (Join-Path $Destination "railway-live-media-$stamp.tar.gz")
}

Write-Host 'Backup finished.' -ForegroundColor Green
