# PM-Hub Admin Local Server Stopper
$port = 8000

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  PM-Hub ローカル管理サーバー 停止スクリプト" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

# ポート8000を使用しているプロセスID(PID)を取得
$netstat = netstat -ano | Select-String ":$port\s+.*LISTENING\s+(\d+)"

if ($netstat) {
    $pidToKill = $netstat.Matches[0].Groups[1].Value
    Write-Host "ポート $port で動作中のサーバープロセス (PID: $pidToKill) を停止しています..." -ForegroundColor Yellow
    Stop-Process -Id $pidToKill -Force -ErrorAction SilentlyContinue
    Write-Host "✅ ローカル管理サーバーを停止しました。" -ForegroundColor Green
} else {
    Write-Host "ℹ️ ポート $port で動作中のサーバープロセスは見つかりませんでした（既に停止しています）。" -ForegroundColor Yellow
}
