"""Готовит строки для самопроверки перевода: тексты пассивок дерева и модов уникальных предметов.

PoB при запуске находит src/Russian/SelfTest/input.txt, переводит каждую строку тем же
кодом, что и при выводе, и пишет пары в src/Russian/SelfTest/output.tsv.
Запуск: python ru/tools/make_selftest.py [версия дерева, по умолчанию последняя]
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"


def tree_lines(version):
	text = (SRC / "TreeData" / version / "tree.lua").read_text(encoding="utf-8")
	lines = set()
	for block in re.findall(r'\["stats"\]=\s*\{(.*?)\}', text, re.S):
		lines.update(s.replace("\\n", "\n") for s in re.findall(r'"((?:[^"\\]|\\.)*)"', block))
	return {l for s in lines for l in s.split("\n") if l.strip()}


def unique_lines():
	lines = set()
	for path in (SRC / "Data" / "Uniques").glob("*.lua"):
		for item in re.findall(r"\[\[(.*?)\]\]", path.read_text(encoding="utf-8"), re.S):
			body = item.strip().splitlines()[2:]
			for line in body:
				line = re.sub(r"\{[^}]*\}", "", line).strip()
				if line and not re.match(r"^(Variant|Requires|Implicits|League|Source|Upgrade|Selected Variant|LevelReq|Sockets|Radius|Limited to|Has Alt Variant)\b", line):
					lines.add(line)
	return lines


def main():
	versions = sorted((p.name for p in (SRC / "TreeData").iterdir() if re.fullmatch(r"\d+_\d+", p.name)),
		key=lambda v: tuple(map(int, v.split("_"))))
	version = sys.argv[1] if len(sys.argv) > 1 else versions[-1]
	lines = sorted(tree_lines(version) | unique_lines())
	out = SRC / "Russian" / "SelfTest"
	out.mkdir(exist_ok=True)
	(out / "input.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
	print(f"Дерево {version}: строк для проверки {len(lines)}")


if __name__ == "__main__":
	main()
