# Обновление русской версии Path of Building.
#
# 1. Подтягивает ветку ru из репозитория (туда GitHub Action вливает обновления upstream).
# 2. Если клиент игры обновился с прошлого запуска, заново выгружает из него русские тексты
#    (ru/tools/export_ggpk.py), пересобирает словарь интерфейса и отправляет изменения в репозиторий.
# 3. Сообщает, сколько строк интерфейса осталось без перевода.
#
# Путь к клиенту берётся из ru/local.json ({"client": "..."}), по умолчанию - Steam-библиотека на D:.
# Запуск: "Обновить PoB.cmd" в корне репозитория или powershell -File ru\update.ps1 [-Force]
param(
	[switch]$Force
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$env:PYTHONIOENCODING = 'utf-8'

function Step($text) { Write-Host "`n== $text" -ForegroundColor Cyan }

$client = 'D:\SteamLibrary\steamapps\common\Path of Exile'
$configPath = Join-Path $PSScriptRoot 'local.json'
if (Test-Path $configPath) {
	$config = Get-Content $configPath -Raw -Encoding UTF8 | ConvertFrom-Json
	if ($config.client) { $client = $config.client }
}

Step 'Обновление из репозитория'
git pull --ff-only origin ru
if ($LASTEXITCODE -ne 0) {
	Write-Host 'Не удалось подтянуть обновления (есть локальные изменения?). Продолжаю с текущей версией.' -ForegroundColor Yellow
}

Step 'Проверка клиента игры'
$index = Join-Path $client 'Bundles2\_.index.bin'
if (-not (Test-Path $index)) { $index = Join-Path $client 'Content.ggpk' }
if (-not (Test-Path $index)) {
	Write-Host "Клиент не найден: $client. Укажите путь в ru\local.json: {`"client`": `"...`"}" -ForegroundColor Red
	exit 1
}
$info = Get-Item $index
$signature = "$($info.Length)-$($info.LastWriteTimeUtc.Ticks)"
$statePath = Join-Path $PSScriptRoot '.client_state'
$previous = if (Test-Path $statePath) { (Get-Content $statePath -Raw).Trim() } else { '' }

if ($Force -or $signature -ne $previous) {
	if (-not (Test-Path 'src\Export\ggpk\bun_extract_file.exe')) {
		Write-Host 'Нет src\Export\ggpk\bun_extract_file.exe (релиз github.com/zao/ooz, см. src\Export\ggpk\README.md).' -ForegroundColor Red
		exit 1
	}
	Write-Host 'Клиент обновился - выгружаю русские тексты...'
	python ru\tools\export_ggpk.py $client
	if ($LASTEXITCODE -ne 0) { throw 'Выгрузка данных из клиента завершилась с ошибкой' }
	python ru\tools\build_ui.py
	if ($LASTEXITCODE -ne 0) { throw 'Сборка словаря интерфейса завершилась с ошибкой' }

	$changes = git status --porcelain -- src/Russian/Data
	if ($changes) {
		Step 'Отправка обновлённых данных'
		git add -- src/Russian/Data
		git commit -m "Русские данные из клиента игры, $(Get-Date -Format 'yyyy-MM-dd')"
		git push origin ru
		if ($LASTEXITCODE -ne 0) {
			git pull --rebase origin ru
			git push origin ru
		}
	} else {
		Write-Host 'Данные не изменились.'
	}
	Set-Content -Path $statePath -Value $signature -Encoding ASCII
} else {
	Write-Host 'Клиент не менялся с прошлой выгрузки.'
}

Step 'Строки интерфейса без перевода'
$todo = @(python ru\tools\extract_ui_strings.py | Where-Object { $_ })
Write-Host "Без перевода: $($todo.Count)"
if ($todo.Count -gt 0) {
	$todo | Set-Content -Path (Join-Path $PSScriptRoot 'ui_todo.txt') -Encoding UTF8
	Write-Host 'Список: ru\ui_todo.txt'
}

Step 'Готово'
