# backend_patch/apply.ps1
# 用法: 在 trading-toolkit-web 项目根目录下运行:  powershell -ExecutionPolicy Bypass -File .\backend_patch\apply.ps1
# 作用: 把 backend_patch 中的封闭式基金后端补丁应用到 d:\Develop\GitHub\trading-toolkit-service\cloudrun\

$ErrorActionPreference = 'Stop'

$BACKEND = 'd:\Develop\GitHub\trading-toolkit-service\cloudrun'
if (-not (Test-Path $BACKEND)) {
    Write-Host "后端目录不存在: $BACKEND" -ForegroundColor Red
    exit 1
}

Write-Host "==> 应用封闭式基金后端补丁到 $BACKEND" -ForegroundColor Cyan
Write-Host ""

# ---------- 1. 复制新文件: services/closed_end.py ----------
$srcNew = Join-Path $PSScriptRoot 'services\closed_end.py'
$dstNew = Join-Path $BACKEND 'services\closed_end.py'
Copy-Item -Path $srcNew -Destination $dstNew -Force
Write-Host "[OK] 新增: services\closed_end.py" -ForegroundColor Green

# ---------- 2. 修改 services/base.py: 添加抽象方法 ----------
$baseFile = Join-Path $BACKEND 'services\base.py'
$baseContent = Get-Content $baseFile -Raw -Encoding UTF8

if ($baseContent -notmatch 'get_closed_end_list') {
    # 在 health_check 抽象方法前插入新方法
    $newMethods = @'
    @abstractmethod
    def get_closed_end_list(self) -> list:
        """获取封闭式基金列表（含价格、净值、折价率）"""

    @abstractmethod
    def get_closed_end_summary(self) -> dict:
        """获取封闭式基金市场概览'''

    # 用 health_check 作为锚点插入
    $pattern = '    @abstractmethod\n    def health_check'
    $replacement = "$newMethods\n\n$0"
    $baseContent = [regex]::Replace($baseContent, $pattern, $replacement, [System.Text.RegularExpressions.RegexOptions]::Multiline)

    # 写回
    Set-Content -Path $baseFile -Value $baseContent -Encoding UTF8 -NoNewline
    Write-Host "[OK] 修改: services\base.py (添加 2 个抽象方法)" -ForegroundColor Green
} else {
    Write-Host "[SKIP] services\base.py 已包含 closed_end 方法" -ForegroundColor Yellow
}

# ---------- 3. 修改 services/akshare_source.py: 添加实现 ----------
$akFile = Join-Path $BACKEND 'services\akshare_source.py'
$akContent = Get-Content $akFile -Raw -Encoding UTF8

# 添加 import
if ($akContent -notmatch 'from services.closed_end import') {
    $akContent = $akContent -replace '(from services.hk_ipo import \()', "from services.closed_end import (`n    get_closed_end_list as _raw_closed_end_list,`n    get_closed_end_summary as _raw_closed_end_summary,`n)`$1"
}

# 添加方法实现 (在 get_hk_ipo_detail 方法之后)
if ($akContent -notmatch 'def get_closed_end_list') {
    $insertCode = @'
    # ---- 封闭式基金 ----

    def get_closed_end_list(self) -> list:
        try:
            return _raw_closed_end_list()
        except Exception as e:
            logger.warning(f'[AkshareSource] get_closed_end_list 失败: {e}')
            return []

    def get_closed_end_summary(self) -> dict:
        try:
            return _raw_closed_end_summary()
        except Exception as e:
            logger.warning(f'[AkshareSource] get_closed_end_summary 失败: {e}')
            return {}

'@
    # 在 # ---- 市场情绪 ---- 之前插入
    $akContent = $akContent -replace '(    # ---- 市场情绪 ----)', "$insertCode`$1"
    Set-Content -Path $akFile -Value $akContent -Encoding UTF8 -NoNewline
    Write-Host "[OK] 修改: services\akshare_source.py (添加 import + 2 个方法)" -ForegroundColor Green
} else {
    Write-Host "[SKIP] services\akshare_source.py 已包含 closed_end 方法" -ForegroundColor Yellow
}

# ---------- 4. 修改 services/efinance_source.py, tushare_source.py, mock_source.py: 添加空实现 ----------
$otherSources = @('efinance_source.py', 'tushare_source.py', 'mock_source.py')
foreach ($src in $otherSources) {
    $file = Join-Path $BACKEND "services\$src"
    if (-not (Test-Path $file)) { continue }
    $content = Get-Content $file -Raw -Encoding UTF8
    if ($content -match 'def get_closed_end_list') {
        Write-Host "[SKIP] services\$src 已包含 closed_end 方法" -ForegroundColor Yellow
        continue
    }
    # 找到 health_check 方法定义位置，在它之前插入
    $insertCode = @'
    def get_closed_end_list(self) -> list:
        return []

    def get_closed_end_summary(self) -> dict:
        return {}

'@
    # 在 def health_check 之前插入
    $content = $content -replace '(    def health_check)', "$insertCode`$1"
    Set-Content -Path $file -Value $content -Encoding UTF8 -NoNewline
    Write-Host "[OK] 修改: services\$src (添加空实现)" -ForegroundColor Green
}

# ---------- 5. 修改 cloudrun/app.py: 添加路由 ----------
$appFile = Join-Path $BACKEND 'app.py'
$appContent = Get-Content $appFile -Raw -Encoding UTF8

if ($appContent -notmatch '/api/v1/closed-end/list') {
    $routeCode = @'
# ==================== 封闭式基金 API ====================

@app.route('/api/v1/closed-end/list')
@limit(60)
def closed_end_list():
    """封闭式基金列表"""
    force = request.args.get('refresh', '').lower() == 'true'
    data, source, cached = fetch_with_cache(
        'closed_end_list', 'get_closed_end_list', force_refresh=force)
    if data is None:
        return api_error(*ErrorCode.DATA_SOURCE_ERROR)
    return api_response(data, source=source, cached=cached)


@app.route('/api/v1/closed-end/summary')
@limit(60)
def closed_end_summary():
    """封闭式基金市场概览"""
    force = request.args.get('refresh', '').lower() == 'true'
    data, source, cached = fetch_with_cache(
        'closed_end_summary', 'get_closed_end_summary', force_refresh=force)
    if data is None:
        return api_error(*ErrorCode.DATA_SOURCE_ERROR)
    return api_response(data, source=source, cached=cached)


'@
    # 在 "# ==================== 管理接口" 之前插入
    $appContent = $appContent -replace '(# ==================== 管理接口)', "$routeCode`$1"
    Set-Content -Path $appFile -Value $appContent -Encoding UTF8 -NoNewline
    Write-Host "[OK] 修改: cloudrun\app.py (添加 2 个路由)" -ForegroundColor Green
} else {
    Write-Host "[SKIP] cloudrun\app.py 已包含 closed-end 路由" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "==> 补丁应用完成!" -ForegroundColor Cyan
Write-Host "==> 下一步: 重启后端 Flask 服务" -ForegroundColor Cyan
Write-Host "    1. 停止当前后端进程 (Ctrl+C)" -ForegroundColor Gray
Write-Host "    2. 进入 d:\Develop\GitHub\trading-toolkit-service" -ForegroundColor Gray
Write-Host "    3. 运行: py cloudrun\app.py" -ForegroundColor Gray
