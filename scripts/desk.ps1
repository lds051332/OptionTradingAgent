param(
    [switch]$Dev,
    [switch]$Stop,
    [switch]$Build,
    [switch]$NoBuild
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$Root = Split-Path -Parent $PSScriptRoot
if (-not (Test-Path (Join-Path $Root "pyproject.toml"))) {
    throw "找不到仓库根目录（pyproject.toml）。请从仓库里运行 desk.cmd。"
}
Set-Location $Root

$WebDir = Join-Path $Root "web"
$EnvFile = Join-Path $Root ".env"
$EnvExample = Join-Path $Root ".env.example"
$VenvPython = Join-Path $Root ".venv\Scripts\python.exe"
$DefaultPort = 8000
$VitePort = 5173

function Write-Step([string]$Message) {
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Write-Warn([string]$Message) {
    Write-Host "!!  $Message" -ForegroundColor Yellow
}

function Get-DotEnvValue([string]$Key) {
    if (-not (Test-Path $EnvFile)) {
        return $null
    }
    foreach ($line in Get-Content -LiteralPath $EnvFile -Encoding UTF8) {
        $trim = $line.Trim()
        if ($trim.StartsWith("#") -or -not $trim.Contains("=")) {
            continue
        }
        $name, $value = $trim.Split("=", 2)
        if ($name.Trim() -eq $Key) {
            return $value.Trim().Trim("'").Trim('"')
        }
    }
    return $null
}

function Get-ListenPort {
    $raw = Get-DotEnvValue "OPTION_DESK_WEB_PORT"
    if ($raw -and $raw -match "^\d+$") {
        return [int]$raw
    }
    return $DefaultPort
}

function Get-PidsOnPort([int]$Port) {
    $ids = New-Object System.Collections.Generic.List[int]
    try {
        $found = Get-NetTCPConnection -LocalPort $Port -ErrorAction Stop |
            Select-Object -ExpandProperty OwningProcess -Unique
        foreach ($id in @($found)) {
            if ($id -and $id -gt 4) { [void]$ids.Add([int]$id) }
        }
    } catch {
        $pattern = (":{0}\s" -f $Port)
        foreach ($line in (netstat -ano | Select-String $pattern)) {
            if ($line.Line -match "\s(\d+)\s*$") {
                $id = [int]$Matches[1]
                if ($id -gt 4) { [void]$ids.Add($id) }
            }
        }
    }
    return $ids | Select-Object -Unique
}

function Stop-CommandMatches([string]$Pattern) {
    try {
        Get-CimInstance Win32_Process -ErrorAction Stop |
            Where-Object { $_.CommandLine -and $_.CommandLine -match $Pattern } |
            ForEach-Object {
                if ($_.ProcessId -gt 4) {
                    Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
                }
            }
    } catch {
        # CIM not available; port kill below is enough.
    }
}

function Stop-Desk([int]$Port) {
    Write-Step "停止已有服务（端口 $Port / $VitePort，以及 option_desk.web / vite）"
    Stop-CommandMatches "option_desk\.web|option-desk-web"
    if ($Dev -or $Stop) {
        Stop-CommandMatches "vite"
    }
    foreach ($id in @(Get-PidsOnPort $Port) + @(Get-PidsOnPort $VitePort)) {
        if ($id -and $id -ne $PID) {
            Stop-Process -Id $id -Force -ErrorAction SilentlyContinue
        }
    }
    Start-Sleep -Milliseconds 400
}

function Ensure-EnvFile {
    if (-not (Test-Path $EnvFile)) {
        if (-not (Test-Path $EnvExample)) {
            throw "找不到 .env 或 .env.example"
        }
        Copy-Item $EnvExample $EnvFile
        Write-Warn "已复制 .env.example → .env，请补 LLM key 和口令"
    }
    $password = Get-DotEnvValue "OPTION_DESK_WEB_PASSWORD"
    if (-not $password) {
        Add-Content -LiteralPath $EnvFile -Value "`nOPTION_DESK_WEB_PASSWORD=desk"
        Write-Warn "OPTION_DESK_WEB_PASSWORD 为空，已写入本机默认口令 desk（上云请改掉）"
    }
    $secret = Get-DotEnvValue "OPTION_DESK_WEB_SECRET"
    if (-not $secret -or $secret -eq "change-me-to-a-long-random-string") {
        $generated = -join ((1..32) | ForEach-Object { "{0:x}" -f (Get-Random -Max 16) })
        $text = Get-Content -LiteralPath $EnvFile -Raw -Encoding UTF8
        if ($text -match "(?m)^OPTION_DESK_WEB_SECRET=.*$") {
            $text = [regex]::Replace($text, "(?m)^OPTION_DESK_WEB_SECRET=.*$", "OPTION_DESK_WEB_SECRET=$generated")
        } else {
            $text = $text.TrimEnd() + "`r`nOPTION_DESK_WEB_SECRET=$generated`r`n"
        }
        Set-Content -LiteralPath $EnvFile -Value $text -Encoding UTF8 -NoNewline
        Write-Warn "已生成本机 OPTION_DESK_WEB_SECRET"
    }
}

function Get-Uv {
    return Get-Command uv -ErrorAction SilentlyContinue
}

function Ensure-Python {
    if (-not (Test-Path $VenvPython)) {
        Write-Step "创建虚拟环境 .venv"
        $uv = Get-Uv
        if ($uv) {
            & $uv.Source venv .venv
        } else {
            $py = Get-Command py -ErrorAction SilentlyContinue
            if ($py) { & $py.Source -3 -m venv .venv }
            else { python -m venv .venv }
        }
    }
    if (-not (Test-Path $VenvPython)) {
        throw "无法创建 .venv\Scripts\python.exe"
    }
    & $VenvPython -c "import option_desk.web, fastapi, uvicorn" 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Step "安装 Python 依赖"
        $uv = Get-Uv
        if ($uv) {
            & $uv.Source pip install -e ".[dev]" --python $VenvPython
        } else {
            & $VenvPython -m pip install -e ".[dev]"
        }
        if ($LASTEXITCODE -ne 0) {
            throw "Python 依赖安装失败"
        }
    }
    return $VenvPython
}

function Test-FrontendStale {
    $distIndex = Join-Path $WebDir "dist\index.html"
    if (-not (Test-Path $distIndex)) {
        return $true
    }
    $distTime = (Get-Item $distIndex).LastWriteTimeUtc
    $markers = @(
        (Join-Path $WebDir "package.json"),
        (Join-Path $WebDir "package-lock.json"),
        (Join-Path $WebDir "index.html"),
        (Join-Path $WebDir "vite.config.ts")
    )
    foreach ($path in $markers) {
        if ((Test-Path $path) -and (Get-Item $path).LastWriteTimeUtc -gt $distTime) {
            return $true
        }
    }
    $src = Join-Path $WebDir "src"
    if (Test-Path $src) {
        $newer = Get-ChildItem -LiteralPath $src -Recurse -File -ErrorAction SilentlyContinue |
            Where-Object { $_.LastWriteTimeUtc -gt $distTime } |
            Select-Object -First 1
        if ($newer) { return $true }
    }
    return $false
}

function Ensure-Frontend([bool]$ForceBuild, [bool]$SkipBuild) {
    $npm = Get-Command npm.cmd -ErrorAction SilentlyContinue
    if (-not $npm) { $npm = Get-Command npm -ErrorAction SilentlyContinue }
    if (-not $npm) {
        if (-not (Test-Path (Join-Path $WebDir "dist\index.html"))) {
            throw "未安装 Node.js/npm，且 web/dist 不存在。请安装 Node 20+ 或先在有 Node 的机器上 build。"
        }
        Write-Warn "未找到 npm，跳过前端构建，使用现有 web/dist"
        return
    }
    $nodeModules = Join-Path $WebDir "node_modules"
    if (-not (Test-Path $nodeModules)) {
        Write-Step "npm install"
        Push-Location $WebDir
        try { & $npm.Source install } finally { Pop-Location }
        if ($LASTEXITCODE -ne 0) { throw "npm install 失败" }
    }
    $needBuild = $ForceBuild -or ((-not $SkipBuild) -and (Test-FrontendStale))
    if ($SkipBuild -and -not (Test-Path (Join-Path $WebDir "dist\index.html"))) {
        $needBuild = $true
        Write-Warn "指定了 -NoBuild 但 dist 不存在，仍会构建一次"
    }
    if ($needBuild) {
        Write-Step "构建前端 web/dist"
        Push-Location $WebDir
        try { & $npm.Source run build } finally { Pop-Location }
        if ($LASTEXITCODE -ne 0) { throw "npm run build 失败" }
    } else {
        Write-Step "前端 dist 已是最新，跳过构建"
    }
}

function Start-Dev([string]$Python, [int]$Port) {
    $npm = Get-Command npm.cmd -ErrorAction SilentlyContinue
    if (-not $npm) { $npm = Get-Command npm -ErrorAction SilentlyContinue }
    if (-not $npm) { throw "开发模式需要 Node.js / npm" }
    $nodeModules = Join-Path $WebDir "node_modules"
    if (-not (Test-Path $nodeModules)) {
        Write-Step "npm install"
        Push-Location $WebDir
        try { & $npm.Source install } finally { Pop-Location }
    }
    Write-Step "启动 API :$Port 和 Vite :$VitePort（Ctrl+C 会停掉两边）"
    $api = Start-Process -FilePath $Python -ArgumentList "-m", "option_desk.web" -WorkingDirectory $Root -PassThru -WindowStyle Hidden
    $vite = $null
    try {
        $vite = Start-Process -FilePath $npm.Source -ArgumentList "run", "dev" -WorkingDirectory $WebDir -PassThru -NoNewWindow
        Wait-Process -Id $vite.Id
    } finally {
        if ($vite -and -not $vite.HasExited) { Stop-Process -Id $vite.Id -Force -ErrorAction SilentlyContinue }
        if ($api -and -not $api.HasExited) { Stop-Process -Id $api.Id -Force -ErrorAction SilentlyContinue }
        Stop-Desk $Port
    }
}

try {
    $Port = Get-ListenPort
    Stop-Desk $Port
    if ($Stop) {
        Write-Host "已停止。" -ForegroundColor Green
        exit 0
    }

    Ensure-EnvFile
    $Python = Ensure-Python

    if ($Dev) {
        Start-Dev $Python $Port
        exit 0
    }

    Ensure-Frontend -ForceBuild:$Build.IsPresent -SkipBuild:$NoBuild.IsPresent
} catch {
    Write-Host $_ -ForegroundColor Red
    exit 2
}

$Password = Get-DotEnvValue "OPTION_DESK_WEB_PASSWORD"
Write-Host ""
Write-Host "本机决策台: http://127.0.0.1:$Port" -ForegroundColor Green
if ($Password) {
    Write-Host "登录口令:   $Password" -ForegroundColor Green
}
Write-Host "Ctrl+C 停止。再执行本脚本即重启。" -ForegroundColor DarkGray
Write-Host ""
& $Python -m option_desk.web
exit $LASTEXITCODE
