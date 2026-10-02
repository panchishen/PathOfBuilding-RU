-- Path of Building: русская локализация
--
-- Module: Russian Item Import
-- Переводит текст предмета, скопированный в русском клиенте (Ctrl+C / Ctrl+Alt+C),
-- в английский текст, который понимает разбор предметов PoB (ItemClass:ParseRaw).
--
local russian = ...

local ipairs = ipairs
local t_insert = table.insert
local t_concat = table.concat

-- Обратные словари грузим при первом русском предмете, а не на старте
local namesReverse, statReverse
local function loadReverse()
	if namesReverse then
		return
	end
	local ok
	ok, namesReverse = pcall(LoadModule, "Russian/Data/NamesReverse")
	if not ok or type(namesReverse) ~= "table" then
		ConPrintf("Russian: не удалось загрузить NamesReverse: %s", tostring(namesReverse))
		namesReverse = { }
	end
	ok, statReverse = pcall(LoadModule, "Russian/Data/StatReverse")
	if not ok or type(statReverse) ~= "table" then
		ConPrintf("Russian: не удалось загрузить StatReverse: %s", tostring(statReverse))
		statReverse = { }
	end
end

local function hasCyrillic(text)
	return text:find("[\208\209]") ~= nil
end

-- Значения редкости приходят в разных родах: "Редкий", "Редкая"...
local rarityPrefixes = {
	{ "Обыч", "Normal" },
	{ "Волш", "Magic" },
	{ "Редк", "Rare" },
	{ "Уник", "Unique" },
	{ "Реликв", "Relic" },
	{ "Валют", "Currency" },
	{ "Камен", "Gem" },
}

-- Пометки в конце строки мода
local lineTags = {
	["неявн"] = "(implicit)",
	["implicit"] = "(implicit)",
	["зачаров"] = "(enchant)",
	["enchant"] = "(enchant)",
	["ремесл"] = "(crafted)",
	["crafted"] = "(crafted)",
	["расколот"] = "(fractured)",
	["fractured"] = "(fractured)",
	["руни"] = "(rune)",
	["rune"] = "(rune)",
	["скверн"] = "(scourge)",
	["scourge"] = "(scourge)",
	["crucible"] = "(crucible)",
}

local function reverseStat(text)
	-- Расширенное копирование пишет диапазон после значения: "+45(40-50)"
	text = text:gsub("(%d)%(%-?[%d%.]+%-%-?[%d%.]+%)", "%1")
	-- Десятичная запятая
	text = text:gsub("(%d),(%d)", "%1.%2")
	local key, tokens = russian.NormalizeNumbers(text)
	key = key:gsub("[%+%-]#", "#")
	local variants = statReverse[key]
	if not variants then
		return nil
	end
	for _, variant in ipairs(variants) do
		if #variant.s == #tokens then
			local shown = { }
			for slot, statIndex in ipairs(variant.s) do
				if statIndex then
					shown[statIndex] = tokens[slot]
				end
			end
			return russian.FormatTemplate(variant.e, shown)
		end
	end
end

-- Ищет в строке самое длинное русское название базы предмета (для волшебных и обычных)
local function findBase(line)
	local bestRu, bestEn
	for ru, en in pairs(namesReverse) do
		if (not bestRu or #ru > #bestRu) and data.itemBases[en] and line:find(ru, 1, true) then
			bestRu, bestEn = ru, en
		end
	end
	return bestEn
end

local function translateValue(value)
	if not hasCyrillic(value) then
		return value
	end
	local exact = namesReverse[value]
	if exact then
		return exact
	end
	-- "+20% (усилено)" - русские пометки в скобках разбор не использует
	local stripped = value:gsub("%s*%([^)]*[\208\209][^)]*%)", "")
	if not hasCyrillic(stripped) then
		return stripped
	end
	return value
end

local function translateLine(line)
	if not hasCyrillic(line) then
		return line
	end
	-- Сначала шаблоны модов: в названиях ключевое умение "Проводник" - это пассивка
	-- "The Conduit", а на предмете тот же текст - мод "Conduit"
	local stat = reverseStat(line)
	if stat then
		return stat, true
	end
	local exact = namesReverse[line]
	if exact then
		return exact
	end
	local label, value = line:match("^([^:]+):%s*(.*)$")
	if label then
		local enLabel = namesReverse[label]
		if enLabel then
			if value == "" then
				return enLabel .. ":"
			end
			return enLabel .. ": " .. translateValue(value)
		end
	end
	return line
end

-- Переводит строку мода с пометкой "(implicit)" и т.п. в конце.
-- Возвращает текст, признак "распознан как мод" и признак "пометка уже есть".
local function translateModLine(line)
	local body, tag = line:match("^(.-)%s*(%b())$")
	if body and body ~= "" then
		local lowerTag = tag:lower()
		for prefix, enTag in pairs(lineTags) do
			if lowerTag:find(prefix, 1, true) then
				local text, isStat = translateLine(body)
				return text .. " " .. enTag, isStat, true
			end
		end
	end
	local text, isStat = translateLine(line)
	return text, isStat, false
end

-- В блоке требований разбор PoB ждёт сокращённые названия атрибутов
local requirementLabels = {
	Strength = "Str",
	Dexterity = "Dex",
	Intelligence = "Int",
}

-- Русский клиент не помечает неявные свойства и зачарования: их выдаёт только
-- отдельный блок. Блоки модов после "Item Level": если их два, первый - неявные;
-- если три - зачарование и неявные.
local function tagModSections(out, statLines, itemLevelIndex)
	if not itemLevelIndex then
		return
	end
	local sections = { }
	local current
	for index = itemLevelIndex + 1, #out do
		if out[index] == "--------" then
			current = nil
		elseif statLines[index] ~= nil then
			if not current then
				current = { }
				t_insert(sections, current)
			end
			t_insert(current, index)
		end
	end
	local tags = #sections >= 3 and { "(enchant)", "(implicit)" } or #sections == 2 and { "(implicit)" } or { }
	for sectionIndex, tag in ipairs(tags) do
		for _, index in ipairs(sections[sectionIndex]) do
			if statLines[index] then
				out[index] = out[index] .. " " .. tag
			end
		end
	end
end

function russian.ItemToEnglish(raw)
	loadReverse()
	local lines = { }
	for line in (raw:gsub("\r", "") .. "\n"):gmatch("([^\n]*)\n") do
		t_insert(lines, (line:gsub("^%s+", ""):gsub("%s+$", "")))
	end

	local out = { }
	local rarity
	local nameLines = nil -- строки имени и базы, идут сразу после редкости
	local inRequirements = false
	local itemLevelIndex
	-- Индекс строки в out -> true, если это распознанный мод без пометки;
	-- false, если пометка уже стоит (блок модов, но дописывать не нужно)
	local statLines = { }
	-- Пометка из заголовка расширенного копирования для следующих строк блока
	local headerTag
	for _, line in ipairs(lines) do
		-- Приписка расширенного копирования у ключевых умений и т.п.
		line = line:gsub("%s*— Неизменяемое значение$", "")
		local label, value = line:match("^([^:]+):%s*(.*)$")
		local enLabel = label and hasCyrillic(label) and namesReverse[label]
		if line:match("^{") then
			-- Заголовок расширенного копирования: "{ Собственное свойство — ... }" - неявное,
			-- остальные (префикс, суффикс, уникальное) разбору не нужны
			if line:find("Собственное", 1, true) then
				headerTag = "(implicit)"
			elseif line:find("Зачаров", 1, true) then
				headerTag = "(enchant)"
			else
				headerTag = nil
			end
		elseif line:match("^%(.*%)$") and hasCyrillic(line) then
			-- Справочный текст в скобках под модом
		elseif enLabel == "Rarity" then
			for _, pair in ipairs(rarityPrefixes) do
				if value:find(pair[1], 1, true) == 1 then
					rarity = pair[2]
					break
				end
			end
			-- Окно ручного ввода само дописывает английскую редкость первой строкой
			if out[1] and out[1]:match("^Rarity: ") then
				table.remove(out, 1)
			end
			t_insert(out, "Rarity: " .. (rarity or value))
			nameLines = { }
		elseif nameLines and line ~= "--------" then
			t_insert(nameLines, line)
		else
			if nameLines then
				-- Имя и база: у редких и уникальных две строки, у прочих одна с базой внутри
				if #nameLines >= 2 then
					t_insert(out, translateValue(nameLines[1]))
					t_insert(out, namesReverse[nameLines[2]] or nameLines[2])
				elseif nameLines[1] then
					local name = nameLines[1]
					t_insert(out, namesReverse[name] or (hasCyrillic(name) and findBase(name)) or name)
				end
				nameLines = nil
			end
			if line == "--------" then
				inRequirements = false
				headerTag = nil
				t_insert(out, line)
			elseif enLabel then
				if inRequirements then
					enLabel = requirementLabels[enLabel] or enLabel
				elseif enLabel == "Evasion" then
					-- Английский клиент пишет "Evasion Rating", и по нему PoB различает
					-- варианты Two-Toned Boots
					enLabel = "Evasion Rating"
				end
				t_insert(out, enLabel .. (value ~= "" and (": " .. translateValue(value)) or ":"))
				if enLabel == "Requirements" then
					inRequirements = true
				elseif enLabel == "Item Level" then
					itemLevelIndex = #out
				end
			elseif line ~= "" then
				local text, isStat, hasTag = translateModLine(line)
				if headerTag and not hasTag then
					text = text .. " " .. headerTag
					hasTag = true
				end
				t_insert(out, text)
				if isStat then
					statLines[#out] = not hasTag
				end
			end
		end
	end
	tagModSections(out, statLines, itemLevelIndex)
	return t_concat(out, "\n")
end

-- sanitiseText заменяет всё не-ASCII на "?": сохраняем кириллицу (имена редких предметов),
-- шрифты её теперь выводят
local sanitise = sanitiseText
function sanitiseText(text)
	if not text or not hasCyrillic(text) then
		return sanitise(text)
	end
	local saved = { }
	local protected = text:gsub("[\208\209][\128-\191]", function(char)
		t_insert(saved, char)
		return "\1"
	end)
	local index = 0
	return (sanitise(protected):gsub("\1", function()
		index = index + 1
		return saved[index]
	end))
end

-- Самопроверка: SelfTest/items_ru.txt (предметы через "====") -> SelfTest/items_out.txt
function russian.SelfTestItems()
	local input = io.open("Russian/SelfTest/items_ru.txt", "r")
	if not input then
		return
	end
	local text = input:read("*a")
	input:close()
	local out = io.open("Russian/SelfTest/items_out.txt", "w")
	for raw in (text .. "\n====\n"):gmatch("(.-)\n====\n") do
		local ok, item = pcall(function() return new("Item"):Item(raw) end)
		if ok and item then
			out:write(russian.ItemToEnglish(raw), "\n")
			out:write(string.format(">> база: %s, редкость: %s, имя: %s\n", tostring(item.baseName), tostring(item.rarity), tostring(item.title or item.name)))
			for _, list in ipairs({ item.implicitModLines or { }, item.explicitModLines or { } }) do
				for _, modLine in ipairs(list) do
					out:write(">> ", modLine.extra and "НЕ РАЗОБРАНО: " or "ок: ", modLine.line, "\n")
				end
			end
		else
			out:write(">> ошибка: ", tostring(item), "\n")
		end
		out:write("====\n")
	end
	out:close()
end

-- Перевод на входе конструктора предмета, до sanitiseText: тот заменяет всё не-ASCII на "?".
-- Срабатывает только на тексте с кириллицей.
LoadModule("Classes/Item")
local itemClass = common.classes.Item
local itemConstructor = itemClass.Item
function itemClass:Item(raw, ...)
	if type(raw) == "string" and hasCyrillic(raw) and raw:find("\n") then
		local ok, converted = pcall(russian.ItemToEnglish, raw)
		if ok then
			raw = converted
		else
			ConPrintf("Russian: ошибка импорта предмета: %s", tostring(converted))
		end
	end
	return itemConstructor(self, raw, ...)
end
