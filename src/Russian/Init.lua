-- Path of Building: русская локализация
--
-- Module: Russian Init
-- Переводит текст на этапе вывода: перехватывает DrawString/DrawStringWidth и перенос
-- строк, а расчётный код PoB продолжает работать с английскими строками.
--
-- Источники перевода, по порядку:
--   Data/UI.lua               - строки интерфейса PoB (машинный перевод, правится вручную);
--   Data/Names.lua            - официальные названия из клиента игры;
--   Data/StatDescriptions.lua - официальные описания статов (тексты модов) из клиента.
-- Не найденные строки копятся в Missing.txt, чтобы их можно было допереводить.
--
local main = ...

local pairs = pairs
local ipairs = ipairs
local tonumber = tonumber
local t_insert = table.insert
local t_concat = table.concat
local s_find = string.find
local s_sub = string.sub
local s_gsub = string.gsub

local russian = { }
_G.russian = russian

local function loadData(name)
	local ok, data = pcall(LoadModule, "Russian/Data/" .. name)
	if ok and type(data) == "table" then
		return data
	end
	ConPrintf("Russian: не удалось загрузить %s: %s", name, tostring(data))
	local log = io.open("Russian/Errors.log", "a")
	if log then
		log:write(os.date("%Y-%m-%d %H:%M:%S "), name, ": ", tostring(data), "\n")
		log:close()
	end
	return { }
end

local uiStrings = loadData("UI")
local names = loadData("Names")
local statDescriptions = loadData("StatDescriptions")

-- ============================================================ описания статов

-- Заменяет числа и диапазоны вида "(10-20)" на "#" и возвращает ключ шаблона и список чисел
local function normalizeNumbers(text)
	local tokens = { }
	local out = { }
	local pos = 1
	local len = #text
	while pos <= len do
		local s, e = s_find(text, "[%+%-]?%(%-?%d+%.?%d*%-%-?%d+%.?%d*%)", pos)
		local s2, e2 = s_find(text, "[%+%-]?%d+", pos)
		if s2 and (not s or s2 < s) then
			s, e = s2, e2
			-- Дробная часть, но не точка в конце предложения
			local frac = text:match("^%.%d+", e + 1)
			if frac then
				e = e + #frac
			end
		end
		if not s then
			break
		end
		t_insert(out, s_sub(text, pos, s - 1))
		t_insert(out, "#")
		t_insert(tokens, s_sub(text, s, e))
		pos = e + 1
	end
	t_insert(out, s_sub(text, pos))
	return t_concat(out), tokens
end

local function tokenValue(token)
	local num = token:match("^[%+%-]?%(?(%-?%d+%.?%d*)")
	num = tonumber(num) or 0
	if token:match("^%-") then
		num = -num
	end
	return num
end

local function limitsMatch(limits, values)
	for index, limit in ipairs(limits) do
		local value = values[index - 1]
		if value then
			if limit[1] == "!" then
				if value == limit[2] then
					return false
				end
			else
				if limit[1] ~= "#" and value < limit[1] then
					return false
				end
				if limit[2] ~= "#" and value > limit[2] then
					return false
				end
			end
		end
	end
	return true
end

local function negateValues(values)
	local out = { }
	for k, v in pairs(values) do
		out[k] = -v
	end
	return out
end

local function formatTemplate(template, shown)
	local auto = 0
	return (s_gsub(template, "{(%d*):?([^}]*)}", function(index, fmt)
		local statIndex = tonumber(index)
		if not statIndex then
			statIndex = auto
			auto = auto + 1
		end
		local token = shown[statIndex]
		if not token then
			return "{" .. index .. "}"
		end
		token = token:gsub("^%+", "")
		if fmt == "+d" and not token:match("^%-") then
			token = "+" .. token
		end
		return token
	end))
end

local function translateStat(text)
	local key, tokens = normalizeNumbers(text)
	key = s_gsub(key, "[%+%-]#", "#")
	local variants = statDescriptions[key]
	if not variants then
		return nil
	end
	for _, variant in ipairs(variants) do
		if #variant.s == #tokens then
			-- Значения статов в том виде, как они показаны в английской строке
			local shown, values = { }, { }
			for slot, statIndex in ipairs(variant.s) do
				if statIndex then
					shown[statIndex] = tokens[slot]
					values[statIndex] = tokenValue(tokens[slot])
				end
			end
			-- Строки "reduced"/"less" показывают модуль отрицательного значения
			if not limitsMatch(variant.l, values) and limitsMatch(variant.l, negateValues(values)) then
				values = negateValues(values)
			end
			local line
			if #variant.r == variant.n then
				line = variant.r[variant.i]
			else
				for _, ruLine in ipairs(variant.r) do
					if limitsMatch(ruLine.l, values) then
						line = ruLine
						break
					end
				end
			end
			line = line or variant.r[1]
			return formatTemplate(line.t, shown)
		end
	end
end

-- ============================================================ общий перевод строк

local missing = { }
local missingDirty = false

local function noteMissing(text)
	if not missing[text] and #text > 1 and text:match("%a%a") then
		missing[text] = true
		missingDirty = true
	end
end

local translateSegment

-- Перевод фрагмента без цветовых кодов
translateSegment = function(text)
	local lead, body, trail = text:match("^(%s*)(.-)(%s*)$")
	if body == "" or not body:match("%a") then
		return text
	end
	local result = uiStrings[body] or names[body] or translateStat(body)
	if not result then
		-- "Подпись: значение"
		local label, sep, value = body:match("^(.-)(:%s*)(.*)$")
		if label and label ~= "" then
			local trLabel = uiStrings[label] or names[label]
			if trLabel then
				result = trLabel .. sep .. (value ~= "" and translateSegment(value) or "")
			end
		end
	end
	if not result then
		noteMissing(body)
		return text
	end
	return lead .. result .. trail
end

local cache = { }
local cacheSize = 0

-- Переводит строку целиком, сохраняя цветовые коды ^7 и ^xRRGGBB
function russian.Translate(text)
	if type(text) ~= "string" or text == "" then
		return text
	end
	local cached = cache[text]
	if cached then
		return cached
	end
	local result
	if s_find(text, "[\208\209]") or not s_find(text, "%a") then
		-- Уже по-русски или без слов
		result = text
	else
		local parts = { }
		local pos = 1
		while true do
			local s, e = s_find(text, "%^x%x%x%x%x%x%x", pos)
			local s2, e2 = s_find(text, "%^%d", pos)
			if s2 and (not s or s2 < s) then
				s, e = s2, e2
			end
			if not s then
				break
			end
			t_insert(parts, translateSegment(s_sub(text, pos, s - 1)))
			t_insert(parts, s_sub(text, s, e))
			pos = e + 1
		end
		t_insert(parts, translateSegment(s_sub(text, pos)))
		result = t_concat(parts)
	end
	if cacheSize > 50000 then
		cache = { }
		cacheSize = 0
	end
	cache[text] = result
	cacheSize = cacheSize + 1
	return result
end

local translate = russian.Translate

-- ============================================================ перехват вывода

-- Пока > 0, текст выводится как есть (например, содержимое полей ввода)
russian.suspend = 0

local drawString = DrawString
local drawStringWidth = DrawStringWidth
local drawStringCursorIndex = DrawStringCursorIndex

-- Если задано, текст шире этой ширины выводится уменьшенным шрифтом (подписи кнопок)
russian.fitWidth = nil

function DrawString(left, top, align, height, font, text)
	if russian.suspend == 0 then
		text = translate(text)
	end
	local fitWidth = russian.fitWidth
	if fitWidth and type(text) == "string" then
		local width = drawStringWidth(height, font, text)
		if width > fitWidth then
			local fitHeight = math.max(8, math.floor(height * fitWidth / width))
			top = top + math.floor((height - fitHeight) / 2)
			height = fitHeight
		end
	end
	return drawString(left, top, align, height, font, text)
end

function DrawStringWidth(height, font, text)
	if russian.suspend == 0 then
		text = translate(text)
	end
	return drawStringWidth(height, font, text)
end

function DrawStringCursorIndex(height, font, text, cursorX, cursorY)
	if russian.suspend == 0 then
		text = translate(text)
	end
	return drawStringCursorIndex(height, font, text, cursorX, cursorY)
end

-- Переносим строки уже переведёнными, иначе разбиение по английскому тексту рвёт фразы
local wrapString = main.WrapString
function main:WrapString(str, height, width)
	return wrapString(self, translate(str), height, width)
end

-- Поля ввода: подпись переводим, содержимое - нет
LoadModule("Classes/EditControl")
local editClass = common.classes.EditControl
local editDraw = editClass.Draw
function editClass:Draw(...)
	local prompt, placeholder = self.prompt, self.placeholder
	self.prompt = prompt and translate(prompt)
	self.placeholder = placeholder and translate(placeholder)
	russian.suspend = russian.suspend + 1
	local ok, err = pcall(editDraw, self, ...)
	russian.suspend = russian.suspend - 1
	self.prompt, self.placeholder = prompt, placeholder
	if not ok then
		error(err, 0)
	end
end

-- Кнопки имеют фиксированную ширину: длинную русскую подпись ужимаем по ширине
LoadModule("Classes/ButtonControl")
local buttonClass = common.classes.ButtonControl
local buttonDraw = buttonClass.Draw
function buttonClass:Draw(...)
	local width = self:GetSize()
	local prevFit = russian.fitWidth
	russian.fitWidth = width - 4
	local ok, err = pcall(buttonDraw, self, ...)
	russian.fitWidth = prevFit
	if not ok then
		error(err, 0)
	end
end

-- ============================================================ непереведённые строки

function russian.SaveMissing()
	if not missingDirty then
		return
	end
	local list = { }
	for text in pairs(missing) do
		t_insert(list, text)
	end
	table.sort(list)
	local out = io.open("Russian/Missing.txt", "w")
	if out then
		out:write(t_concat(list, "\n"), "\n")
		out:close()
		missingDirty = false
	end
end

local launchExit = launch.OnExit
function launch:OnExit(...)
	russian.SaveMissing()
	return launchExit(self, ...)
end

local launchFrame = launch.OnFrame
local nextSave = 0
function launch:OnFrame(...)
	if GetTime() >= nextSave then
		nextSave = GetTime() + 5000
		russian.SaveMissing()
	end
	return launchFrame(self, ...)
end

-- Самопроверка: если есть SelfTest/input.txt, переводим каждую строку и пишем пары в output.tsv
local selfTestInput = io.open("Russian/SelfTest/input.txt", "r")
if selfTestInput then
	local out = io.open("Russian/SelfTest/output.tsv", "w")
	for line in selfTestInput:lines() do
		out:write(line, "\t", translate(line), "\n")
	end
	out:close()
	selfTestInput:close()
end

local function count(t)
	local n = 0
	for _ in pairs(t) do
		n = n + 1
	end
	return n
end
ConPrintf("Russian: интерфейс %d, названий %d, шаблонов статов %d", count(uiStrings), count(names), count(statDescriptions))

return russian
