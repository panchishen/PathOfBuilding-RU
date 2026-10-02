"""Собирает словарь интерфейса src/Russian/Data/UI.lua из TSV-файлов перевода.

Источники (более поздний перекрывает более ранний):
  ru/ui_tr/*.tsv       - машинный перевод строк интерфейса;
  ru/ui_overrides.tsv  - ручные правки.
Формат строки: "английский<TAB>русский". Строки без перевода (ru == en) пропускаются.

Запуск: python ru/tools/build_ui.py
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).parent))
from export_ggpk import lua_str  # noqa: E402

OUT = ROOT / "src" / "Russian" / "Data" / "UI.lua"


def read_tsv(path):
	pairs = {}
	for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
		line = line.rstrip("\r")
		if not line or line.startswith("#"):
			continue
		if line.count("\t") != 1:
			print(f"{path.name}:{n}: пропущена строка без одной табуляции", file=sys.stderr)
			continue
		en, ru = line.split("\t")
		if en and ru and en != ru:
			pairs[en] = ru
	return pairs


def main():
	pairs = {}
	for path in sorted((ROOT / "ru" / "ui_tr").glob("*.tsv")):
		pairs.update(read_tsv(path))
	overrides = ROOT / "ru" / "ui_overrides.tsv"
	if overrides.exists():
		pairs.update(read_tsv(overrides))
	out = ["-- Строки интерфейса PoB. Собрано ru/tools/build_ui.py из ru/ui_tr/*.tsv и ru/ui_overrides.tsv",
		"local t = {}"]
	for en in sorted(pairs):
		out.append(f"t[{lua_str(en)}]={lua_str(pairs[en])}")
	out.append("return t")
	OUT.write_text("\n".join(out) + "\n", encoding="utf-8")
	print(f"Строк интерфейса: {len(pairs)}")


if __name__ == "__main__":
	main()
