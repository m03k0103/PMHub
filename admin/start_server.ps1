# PM-Hub Admin Local Server Starter
$port = 8000
$url = "http://localhost:8000/admin/admin_dashboard.html"
$scriptPath = Join-Path $PSScriptRoot "server.py"

function Test-PortOpen($server, $port) {
    try {
        $client = New-Object System.Net.Sockets.TcpClient
        $async = $client.BeginConnect($server, $port, $null, $null)
        $wait = $async.AsyncWaitHandle.WaitOne(300, $false)
        if (-not $wait) {
            $client.Close()
            return $false
        }
        $client.EndConnect($async)
        $client.Close()
        return $true
    } catch {
        return $false
    }
}

Write-Host "[1/3] Checking PM-Hub Server status..." -ForegroundColor Cyan

$isOpen = Test-PortOpen "127.0.0.1" $port

if (-not $isOpen) {
    Write-Host "[2/3] Server is not running. Launching Python server..." -ForegroundColor Yellow
    
    $pyCmd = "py"
    if (Get-Command "python" -ErrorAction SilentlyContinue) { $pyCmd = "python" }
    elseif (Get-Command "python3" -ErrorAction SilentlyContinue) { $pyCmd = "python3" }

    Start-Process -FilePath $pyCmd -ArgumentList "`"$scriptPath`"" -WorkingDirectory $PSScriptRoot

    Write-Host "[3/3] Waiting for server port $port to become ready..." -ForegroundColor Yellow
    $retries = 0
    while ($retries -lt 30) {
        Start-Sleep -Milliseconds 300
        if (Test-PortOpen "127.0.0.1" $port) {
            $isOpen = $true
            break
        }
        $retries++
    }

    if ($isOpen) {
        Write-Host "Server successfully started!" -ForegroundColor Green
    } else {
        Write-Host "Server start wait timed out. Opening browser anyway..." -ForegroundColor Red
    }
} else {
    Write-Host "Server is already running on port $port." -ForegroundColor Green
}

Write-Host "Opening Admin Dashboard: $url" -ForegroundColor Cyan
Start-Process $url
