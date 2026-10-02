"""Рисует строки из растровых шрифтов SimpleGraphic так же, как движок: по .tgf и .tga.

Нужен, чтобы проверить сгенерированные глифы без запуска PoB.
Запуск: python ru/tools/preview_fonts.py <out.png>
"""

import re
import sys
from pathlib import Path

from PIL import Image

FONT_DIR = Path(__file__).resolve().parents[2] / "runtime" / "SimpleGraphic" / "Fonts"

FONTS = ["Liberation Sans", "Liberation Sans Bold", "Bitstream Vera Sans Mono",
	"Fontin", "Fontin Italic", "Fontin SmallCaps", "Fontin SmallCaps Italic"]
SIZES = [14, 16, 20, 28]
TEXT = "Life +45 к максимуму здоровья, Сопротивление огню 75% — «Ёж» №1…"


def load(name, height):
	glyphs, cur, seq = {}, None, 0
	for line in (FONT_DIR / f"{name}.tgf").read_text(encoding="utf-8").splitlines():
		m = re.match(r"HEIGHT (\d+);", line)
		if m:
			cur, seq = int(m.group(1)), 0
			continue
		if cur != height:
			continue
		m = re.match(r"GLYPH\s+(\d+)\s+(\d+)\s+(\d+)\s+(-?\d+)\s+(-?\d+);", line)
		if m:
			glyphs[seq] = tuple(map(int, m.groups()))
			seq += 1
			continue
		m = re.match(r"CGLYPH\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(-?\d+)\s+(-?\d+);", line)
		if m:
			cp, *rest = map(int, m.groups())
			glyphs[cp] = tuple(rest)
	return glyphs, Image.open(FONT_DIR / f"{name}.{height}.tga").convert("RGBA")


def draw(canvas, x, y, name, height, text):
	glyphs, atlas = load(name, height)
	for ch in text:
		g = glyphs.get(ord(ch))
		if g is None:
			x += height // 2
			continue
		gx, gy, w, sl, sr = g
		x += sl
		if w:
			canvas.alpha_composite(atlas.crop((gx, gy, gx + w, gy + height)), (x, y))
		x += w + sr
	return x


def main(out):
	rows = [(n, s) for n in FONTS for s in SIZES]
	canvas = Image.new("RGBA", (1100, sum(s + 8 for _, s in rows) + 10), (20, 20, 24, 255))
	y = 5
	for name, size in rows:
		draw(canvas, 10, y, name, size, f"{name} {size}: {TEXT}")
		y += size + 8
	canvas.save(out)


if __name__ == "__main__":
	main(sys.argv[1])
