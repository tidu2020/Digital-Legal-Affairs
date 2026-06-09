$ErrorActionPreference = "Stop"
try {
    $r = Invoke-RestMethod -Uri http://127.0.0.1:1824/api/chat -Method Post -InFile "C:\Users\Administrator\Desktop\jingtou-digital-legal\simple_body.json" -ContentType "application/json" -TimeoutSec 180
    $mock = $r.response -match "mock|模拟|模拟模式"
    $preview = $r.response.Substring(0, [Math]::Min(300, $r.response.Length))
    $out = "OK|SESSION=" + $r.session_id + "|LEN=" + $r.response.Length + "|MOCK=" + $mock + "|PREVIEW=" + $preview
    $out | Out-File "C:\Users\Administrator\Desktop\jingtou-digital-legal\chat_final.txt" -Encoding utf8
} catch {
    $err = "ERR|" + $_.Exception.Message
    $err | Out-File "C:\Users\Administrator\Desktop\jingtou-digital-legal\chat_final.txt" -Encoding utf8
}