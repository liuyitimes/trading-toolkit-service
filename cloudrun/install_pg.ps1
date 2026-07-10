# PostgreSQL 本地安装脚本（需管理员权限运行）
# 用法: 右键 PowerShell → 以管理员身份运行 → 执行此脚本
#
# ⚠️ 注意: 这是本地开发脚本，包含硬编码路径（如 .env 文件位置）。
# 请根据实际开发环境修改下方路径后再执行。

Write-Host "=== PostgreSQL 本地安装脚本 ===" -ForegroundColor Cyan

# 1. 检查管理员权限
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "错误: 请以管理员身份运行此脚本！" -ForegroundColor Red
    Write-Host "右键 PowerShell → 以管理员身份运行" -ForegroundColor Yellow
    pause
    exit 1
}

# 2. 安装 PostgreSQL（通过 Chocolatey）
Write-Host "`n[1/4] 安装 PostgreSQL 16..." -ForegroundColor Yellow
choco install postgresql16 --params "/password:postgres" -y

if ($LASTEXITCODE -ne 0) {
    Write-Host "Chocolatey 安装失败，尝试下载安装包..." -ForegroundColor Yellow
    $url = "https://get.enterprisedb.com/postgresql/postgresql-16.14-1-windows-x64.exe"
    $installer = "$env:TEMP\postgresql-installer.exe"
    Write-Host "下载中: $url"
    Invoke-WebRequest -Uri $url -OutFile $installer
    Write-Host "运行安装程序..."
    Start-Process -FilePath $installer -ArgumentList "--mode unattended --superpassword postgres --serverport 5432" -Wait
}

# 3. 等待服务启动
Write-Host "`n[2/4] 等待 PostgreSQL 服务启动..." -ForegroundColor Yellow
Start-Sleep -Seconds 5

# 4. 创建数据库
Write-Host "`n[3/4] 创建 trading_toolkit 数据库..." -ForegroundColor Yellow
$pgBin = "C:\Program Files\PostgreSQL\16\bin"
if (-not (Test-Path $pgBin)) {
    $pgBin = Get-ChildItem "C:\Program Files\PostgreSQL\*\bin" -Directory | Select-Object -First 1 -ExpandProperty FullName
}

if ($pgBin) {
    $env:PGPASSWORD = "postgres"
    & "$pgBin\psql.exe" -U postgres -c "CREATE DATABASE trading_toolkit ENCODING 'UTF8';"
    Write-Host "数据库创建完成" -ForegroundColor Green
} else {
    Write-Host "未找到 PostgreSQL 安装目录，请手动创建数据库" -ForegroundColor Yellow
}

# 5. 创建 .env 文件
Write-Host "`n[4/4] 创建环境配置..." -ForegroundColor Yellow
$envFile = "d:\Develop\WeChatProjects\trading-toolkit\cloudrun\.env"
if (-not (Test-Path $envFile)) {
    @"
# 数据库配置
# SQLite（默认，无需额外配置）
# DATABASE_URL=sqlite:///trading_toolkit.db

# PostgreSQL（安装后取消注释即可切换）
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/trading_toolkit

# 数据源配置
USE_MOCK=false
DATA_SOURCE=akshare
"@ | Out-File -FilePath $envFile -Encoding UTF8
    Write-Host ".env 文件已创建" -ForegroundColor Green
}

Write-Host "`n=== 安装完成 ===" -ForegroundColor Cyan
Write-Host "PostgreSQL 连接信息:" -ForegroundColor White
Write-Host "  用户: postgres" -ForegroundColor White
Write-Host "  密码: postgres" -ForegroundColor White
Write-Host "  数据库: trading_toolkit" -ForegroundColor White
Write-Host "  端口: 5432" -ForegroundColor White
Write-Host "`n切换数据库: 修改 .env 中的 DATABASE_URL" -ForegroundColor Yellow
Write-Host "重启服务: cd cloudrun && python app.py" -ForegroundColor Yellow
pause
