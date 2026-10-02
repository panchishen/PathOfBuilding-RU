"""Собирает из исходников PoB строки, похожие на текст интерфейса, которых ещё нет в переводе.

Строки делятся по цветовым кодам и по "Подпись:" так же, как их режет
src/Russian/Init.lua, чтобы ключи словаря совпадали с тем, что ищется при выводе.
Уже переведённые (Data/UI.lua, Data/Names.lua) и найденные в Missing.txt учитываются.

Запуск: python ru/tools/extract_ui_strings.py > ru/ui_todo.txt
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
SCAN = ["Classes", "Modules", "Launch.lua", "UpdateCheck.lua"]
SKIP_FILES = {"ModParser.lua", "Common.lua", "Data.lua", "ItemTools.lua", "CalcTools.lua", "StatDescriber.lua"}

LITERAL_RE = re.compile(r'"((?:[^"\\\n]|\\.)*)"|\'((?:[^\'\\\n]|\\.)*)\'|\[\[(.*?)\]\]', re.S)
COLOR_RE = re.compile(r"\^x[0-9A-Fa-f]{6}|\^\d")


def lua_keys(path):
	if not path.exists():
		return set()
	return {bytes(m.group(1), "utf-8").decode("unicode_escape").encode("latin-1").decode("utf-8")
		for m in re.finditer(r'^\s*(?:t)?\[\s*"((?:[^"\\]|\\.)*)"\s*\]\s*=', path.read_text(encoding="utf-8"), re.M)}


def looks_like_ui(s):
	if len(s) < 2 or not re.search(r"[A-Za-z]{2}", s):
		return False
	if re.search(r"[%][a-z\[\(]|%[sdwa]|\\[0-9]|^\^|[{}<>]|::|=>|\.lua$|^[a-z_]+$|^[A-Z_0-9]+$|^[\w.\-]*/[\w./\-]*$|\.\.", s):
		return False
	if re.fullmatch(r"[A-Za-z]+[A-Z][a-z]+\w*", s) and " " not in s:  # camelCase идентификатор
		return False
	if re.search(r"\w[.:]\w|^\s|\w\(|	", s):  # фрагменты кода: obj.field, main:Func(, отступы
		return False
	return s[0].isupper() or " " in s.strip()


def segments(literal):
	for part in COLOR_RE.split(literal):
		body = part.strip()
		if not body:
			continue
		m = re.match(r"^(.*?):\s*(.*)$", body)
		if m and m.group(1):
			yield m.group(1).strip()
			if m.group(2):
				yield m.group(2).strip()
		else:
			yield body


def main():
	known = lua_keys(SRC / "Russian" / "Data" / "UI.lua") | lua_keys(SRC / "Russian" / "Data" / "Names.lua")
	# Строки, которые переводчик уже видел (включая оставленные без перевода)
	for tsv in (ROOT / "ru" / "ui_tr").glob("*.tsv"):
		known |= {l.split("	")[0] for l in tsv.read_text(encoding="utf-8").splitlines() if "	" in l}
	found = set()
	files = []
	for item in SCAN:
		p = SRC / item
		files += [p] if p.is_file() else sorted(p.glob("*.lua"))
	for path in files:
		if path.name in SKIP_FILES:
			continue
		text = path.read_text(encoding="utf-8", errors="replace")
		for m in LITERAL_RE.finditer(text):
			literal = next(g for g in m.groups() if g is not None)
			for seg in segments(literal):
				if looks_like_ui(seg) and seg not in known:
					found.add(seg)
	missing = SRC / "Russian" / "Missing.txt"
	if missing.exists():
		found |= {l for l in missing.read_text(encoding="utf-8").splitlines() if l and l not in known}
	sys.stdout.reconfigure(encoding="utf-8")
	for s in sorted(found):
		print(s)


if __name__ == "__main__":
	main()
