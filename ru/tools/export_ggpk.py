"""Выгружает официальные русские тексты из клиента Path of Exile в Lua-данные перевода.

Результат:
  src/Russian/Data/StatDescriptions.lua - английские шаблоны описаний статов и их
      русские варианты (с условиями выбора формы по значению);
  src/Russian/Data/Names.lua            - словарь "английская строка -> русская"
      из локализованных игровых таблиц (скиллы, предметы, пассивки, строки клиента).

Нужен bun_extract_file.exe в src/Export/ggpk (см. src/Export/ggpk/README.md).
Запуск: python ru/tools/export_ggpk.py [путь к клиенту PoE]
"""

import re
import struct
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GGPK_DIR = ROOT / "src" / "Export" / "ggpk"
SPEC = ROOT / "src" / "Export" / "spec.lua"
OUT_DIR = ROOT / "src" / "Russian" / "Data"
DEFAULT_CLIENT = r"D:\SteamLibrary\steamapps\common\Path of Exile"

# ---------------------------------------------------------------- извлечение файлов


def bun(*args, stdin=None):
	return subprocess.run([str(GGPK_DIR / "bun_extract_file.exe"), *args], cwd=GGPK_DIR,
		input=stdin, capture_output=True, text=True, check=True).stdout


def extract(client):
	files = bun("list-files", client).splitlines()
	ruTables = sorted({Path(f).stem for f in files if re.fullmatch(r"data/russian/[a-z0-9_]+\.datc64", f)})
	wanted = [f for f in files if re.fullmatch(r"metadata/statdescriptions/[a-z0-9_]+\.txt", f)]
	wanted += [f"data/{t}.datc64" for t in ruTables] + [f"data/russian/{t}.datc64" for t in ruTables]
	print(f"Извлечение {len(wanted)} файлов...")
	bun("extract-files", client, ".", stdin="\n".join(wanted))
	return ruTables

# ---------------------------------------------------------------- dat64


TYPE_SIZE = {"Bool": 1, "Int": 4, "UInt": 4, "UInt16": 2, "Float": 4, "Enum": 4,
	"Interval": 8, "String": 8, "ShortKey": 8, "Key": 16}


def parse_spec():
	"""spec.lua -> {таблица: [(имя, тип, список)]}."""
	spec, cur, col = {}, None, None
	for line in SPEC.read_text(encoding="utf-8").splitlines():
		m = re.match(r"^\t(\w+)=\{", line)
		if m:
			cur = spec.setdefault(m.group(1), [])
			continue
		if cur is None:
			continue
		if re.match(r"^\t\t\[\d+\]=\{", line):
			col = {}
			cur.append(col)
		elif m := re.match(r'^\t\t\t(\w+)=(?:"(.*)"|(\w+)),?$', line):
			col[m.group(1)] = m.group(2) if m.group(2) is not None else m.group(3)
	return {t: [(c.get("name", ""), c["type"], c.get("list") == "true") for c in cols] for t, cols in spec.items()}


def read_dat(path, cols):
	"""Возвращает {имя столбца: [значения]} для строковых столбцов (в т.ч. списков строк)."""
	raw = path.read_bytes()
	rows = struct.unpack_from("<I", raw)[0]
	dataOff = raw.find(b"\xBB" * 8, 4)
	if rows == 0 or dataOff < 0:
		return None
	rowSize = (dataOff - 4) // rows
	specSize = sum(16 if lst else TYPE_SIZE[t] for _, t, lst in cols)
	if specSize > rowSize:
		return None

	def string_at(off):
		# UTF-16LE с терминатором из четырёх нулевых байт
		start = end = dataOff + off
		while end < len(raw) and raw[end:end + 4] != b"\0\0\0\0":
			end += 2
		return raw[start:end].decode("utf-16-le", errors="replace")

	out = {}
	offset = 0
	for idx, (name, t, lst) in enumerate(cols):
		size = 16 if lst else TYPE_SIZE[t]
		if t == "String":
			key = name or f"#{idx + 1}"
			vals = []
			for r in range(rows):
				base = 4 + r * rowSize + offset
				if lst:
					count, off = struct.unpack_from("<QQ", raw, base)
					vals.append(tuple(string_at(struct.unpack_from("<Q", raw, dataOff + off + i * 8)[0]) for i in range(count)) if count < 1000 else ())
				else:
					vals.append(string_at(struct.unpack_from("<Q", raw, base)[0]))
			out[key] = vals
		offset += size
	return out


# При расхождении перевода одной английской строки побеждает таблица с меньшим номером.
# Слова-аффиксы (words) согласуются по роду и для общих терминов не годятся.
TABLE_PRIORITY = {"clientstrings": 0, "activeskills": 1, "baseitemtypes": 1, "passiveskills": 2,
	"stats": 3, "words": 9}


def build_names(ruTables, spec):
	"""Возвращает (английский -> русский, русский -> английский)."""
	pairs = defaultdict(lambda: defaultdict(Counter))
	reverse = defaultdict(lambda: defaultdict(Counter))
	for table in ruTables:
		cols = spec.get(table)
		if not cols:
			continue
		en = read_dat(GGPK_DIR / "data" / f"{table}.datc64", cols)
		ru = read_dat(GGPK_DIR / "data" / "russian" / f"{table}.datc64", cols)
		if not en or not ru:
			continue
		for col, enVals in en.items():
			if col.lower() in ("id", "hash") or col.endswith("Id"):
				continue
			for e, r in zip(enVals, ru[col]):
				for ev, rv in (zip(e, r) if isinstance(e, tuple) else [(e, r)]):
					if "<if:" in rv:
						# Прилагательные для имён редких предметов, согласуемые по роду
						continue
					ev, rv = clean_markup(ev).strip(), clean_markup(rv).strip()
					if ev and rv and ev != rv and re.search("[А-Яа-яЁё]", rv) and "Metadata/" not in ev:
						pairs[ev][TABLE_PRIORITY.get(table, 5)][rv] += 1
						reverse[rv][TABLE_PRIORITY.get(table, 5)][ev] += 1
	pick = lambda byPrio: byPrio[min(byPrio)].most_common(1)[0][0]
	return {e: pick(p) for e, p in pairs.items()}, {r: pick(p) for r, p in reverse.items()}

# ---------------------------------------------------------------- описания статов


def escape_ggg(text):
	"""Как escapeGGGString в Modules/Common.lua: снимает разметку ссылок GGG."""
	text = re.sub(r"<[^>]+>\{([^}]+)\}", r"\1", text)
	text = re.sub(r"\[([^|\]]+)\]", r"\1", text)
	return re.sub(r"\[[^|\]]+\|([^|\]]+)\]", r"\1", text)


def clean_markup(text):
	"""Снимает разметку GGG и оставляет первый вариант из согласования по роду/числу
	("<if:MS>{Отравляющий}<elif:FS>{Отравляющая}..." -> "Отравляющий")."""
	text = re.sub(r"<if:\w+>\{([^{}]*)\}(?:<elif:\w+>\{[^{}]*\})*(?:<else>\{[^{}]*\})?", r"\1", text)
	return escape_ggg(text)


LINE_RE = re.compile(r'^\s*([\d\-#| !]+?)\s*([A-Za-z_]\w*)?\s*"(.*)"\s*(.*)$')


def parse_limit(tok):
	if tok == "#":
		return ["#", "#"]
	if re.fullmatch(r"-?\d+", tok):
		return [int(tok), int(tok)]
	if m := re.fullmatch(r"!(-?\d+)", tok):
		return ["!", int(m.group(1))]
	a, b = tok.split("|")
	return [int(a) if a != "#" else "#", int(b) if b != "#" else "#"]


def parse_stat_files():
	"""Список описаний: {stats, en: [строки], ru: [строки]}; строка = (лимиты, текст)."""
	descs = []
	seen = set()

	def parse(name):
		if name in seen:
			return
		seen.add(name)
		text = (GGPK_DIR / "metadata" / "statdescriptions" / name).read_bytes().decode("utf-16-le").lstrip("\ufeff")
		cur, lang = None, None
		for line in text.splitlines():
			if m := re.match(r'^include "Metadata/StatDescriptions/(.+)"', line, re.I):
				parse(m.group(1).lower())
				continue
			s = line.strip()
			if s.startswith("no_description") or not s:
				continue
			if s == "description" or s.startswith("description ") or s == "handed_description":
				cur, lang = {"stats": None, "en": [], "ru": []}, "en"
				descs.append(cur)
				continue
			if cur is None:
				continue
			if cur["stats"] is None:
				if m := re.match(r"^\d+\s+(.+)$", s):
					cur["stats"] = m.group(1).split()
				continue
			if m := re.match(r'^lang "(.+)"', s):
				lang = "ru" if m.group(1) == "Russian" else None
				continue
			if lang is None or "table_only" in s:
				continue
			if m := LINE_RE.match(s):
				limits = [parse_limit(t) for t in m.group(1).split()]
				# Перенос строки в файлах клиента записан как два символа "\" и "n"
				cur[lang].append((limits, escape_ggg(m.group(3)).replace("\\n", "\n"), m.group(4)))

	for path in sorted((GGPK_DIR / "metadata" / "statdescriptions").glob("*.txt")):
		if path.name != "skillpopup_stat_filters.txt":
			parse(path.name)
	return [d for d in descs if d["stats"] and d["en"] and d["ru"]]


PLACEHOLDER_RE = re.compile(r"\{(\d*)(?::([^}]*))?\}")
NUMBER_RE = re.compile(r"[+\-]?\d+(?:\.\d+)?")


def normalize_template(text):
	"""Шаблон -> (ключ, слоты): слот = индекс стата или None для литерального числа."""
	slots, out, pos, auto = [], [], 0, 0
	for m in re.finditer(r"\{(\d*)(?::([^}]*))?\}|[+\-]?\d+(?:\.\d+)?", text):
		out.append(text[pos:m.start()])
		if m.group(0).startswith("{"):
			if m.group(1):
				slots.append(int(m.group(1)))
			else:
				slots.append(auto)
				auto += 1
		else:
			slots.append(None)
		out.append("#")
		pos = m.end()
	out.append(text[pos:])
	key = re.sub(r"[+\-]#", "#", "".join(out))
	return key, slots


def lua_str(s):
	return '"' + s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\r", "") + '"'


def lua_limits(limits):
	return "{" + ",".join("{" + ",".join(lua_str(v) if isinstance(v, str) else str(v) for v in l) + "}" for l in limits) + "}"


def write_stat_descriptions(descs):
	entries = {}
	for d in descs:
		for i, (limits, en, _) in enumerate(d["en"]):
			key, slots = normalize_template(en)
			if "#" not in key and not key.strip():
				continue
			ru = tuple((tuple(map(tuple, l)), t) for l, t, _ in d["ru"])
			entries.setdefault(key, {})[(i, len(d["en"]), tuple(map(tuple, limits)), ru)] = slots
			# PoB выводит многострочный мод построчно: если у русских вариантов столько же
			# строк, сколько у английского, сопоставляем строки по порядку
			enParts = en.split("\n")
			if len(enParts) > 1 and all(t.count("\n") == len(enParts) - 1 for _, t in ru):
				for j, part in enumerate(enParts):
					partKey, partSlots = normalize_template(part)
					if partKey.strip():
						ruPart = tuple((l, t.split("\n")[j]) for l, t in ru)
						entries.setdefault(partKey, {})[(i, len(d["en"]), tuple(map(tuple, limits)), ruPart)] = partSlots
	items = []
	for key in sorted(entries):
		variants = []
		for (i, nEn, limits, ru), slots in entries[key].items():
			ruLines = ",".join("{l=" + lua_limits(l) + ",t=" + lua_str(t) + "}" for l, t in ru)
			slotStr = ",".join("false" if s is None else str(s) for s in slots)
			variants.append(f"{{i={i + 1},n={nEn},l={lua_limits(limits)},s={{{slotStr}}},r={{{ruLines}}}}}")
		items.append((key, "{" + ",".join(variants) + "}"))
	write_lua_map(OUT_DIR / "StatDescriptions.lua", items)
	return len(entries)


def limit_range(limit):
	"""Лимит -> (мин, макс) с бесконечностями; "!" трактуется как весь диапазон."""
	if limit[0] == "!":
		return float("-inf"), float("inf")
	lo = float("-inf") if limit[0] == "#" else limit[0]
	hi = float("inf") if limit[1] == "#" else limit[1]
	return lo, hi


def covers(outer, inner):
	"""Каждый диапазон outer содержит соответствующий диапазон inner."""
	if len(outer) != len(inner):
		return False
	for o, i in zip(outer, inner):
		(olo, ohi), (ilo, ihi) = limit_range(o), limit_range(i)
		if not (olo <= ilo and ihi <= ohi):
			return False
	return True


def write_stat_reverse(descs):
	"""Русский шаблон мода -> английский: для импорта предметов из русского клиента."""
	entries = {}

	def add(ruText, enText):
		key, slots = normalize_template(ruText)
		if key.strip():
			entries.setdefault(re.sub(r"[+\-]#", "#", key), {})[enText] = slots

	for d in descs:
		en, ru = d["en"], d["ru"]
		for k, (rl, rt, _) in enumerate(ru):
			match = next((e for e in en if e[0] == rl), None)
			if match is None and len(en) == len(ru):
				match = en[k]
			if match is None:
				match = next((e for e in en if covers(e[0], rl)), None)
			if match is None:
				continue
			et = match[1]
			add(rt, et)
			# Многострочные моды предмет в буфере обмена тоже несёт построчно
			enParts, ruParts = et.split("\n"), rt.split("\n")
			if len(enParts) > 1 and len(enParts) == len(ruParts):
				for ep, rp in zip(enParts, ruParts):
					add(rp, ep)
	items = []
	for key in sorted(entries):
		variants = ",".join("{e=" + lua_str(e) + ",s={" + ",".join("false" if s is None else str(s) for s in slots) + "}}"
			for e, slots in entries[key].items())
		items.append((key, "{" + variants + "}"))
	write_lua_map(OUT_DIR / "StatReverse.lua", items)
	return len(entries)


def write_names(names, reverse):
	write_lua_map(OUT_DIR / "Names.lua", [(e, lua_str(names[e])) for e in sorted(names)])
	write_lua_map(OUT_DIR / "NamesReverse.lua", [(r, lua_str(reverse[r])) for r in sorted(reverse)])


def write_lua_map(path, items):
	"""Пишет пары (ключ, Lua-значение) как PoB пишет Data/ModCache.lua: присваивания
	пачками по 1000 в отдельных функциях, иначе LuaJIT упирается в лимит констант."""
	out = ["-- Сгенерировано ru/tools/export_ggpk.py из файлов клиента, не редактировать вручную",
		"local t = {}", "(function()"]
	for n, (key, value) in enumerate(items, 1):
		out.append(f"t[{lua_str(key)}]={value}")
		if n % 1000 == 0:
			out.append("end)();(function()")
	out += ["end)()", "return t"]
	path.write_text("\n".join(out) + "\n", encoding="utf-8")


def main():
	client = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_CLIENT
	OUT_DIR.mkdir(parents=True, exist_ok=True)
	ruTables = extract(client)
	descs = parse_stat_files()
	print(f"Описаний статов с русским текстом: {len(descs)}, шаблонов: {write_stat_descriptions(descs)}")
	print(f"Обратных шаблонов статов: {write_stat_reverse(descs)}")
	names, reverse = build_names(ruTables, parse_spec())
	write_names(names, reverse)
	print(f"Названий: {len(names)}, обратных: {len(reverse)}")


if __name__ == "__main__":
	main()
