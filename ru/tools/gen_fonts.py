"""Дописывает кириллицу и русскую типографику в растровые шрифты SimpleGraphic.

ASCII-часть атласов (строки GLYPH) не меняется. Новые глифы растеризуются через
Windows GDI тем же способом, что и в PathOfBuilding-FontGenerator, пакуются в
атлас под ASCII-областью и описываются строками "CGLYPH cp x y w sl sr;".
Размер шрифта-донора подбирается так, чтобы высота заглавной "H" и базовая
линия совпадали с оригинальным шрифтом. Скрипт идемпотентен: при повторном
запуске прежние CGLYPH-глифы удаляются и генерируются заново.

Запуск: python ru/tools/gen_fonts.py
"""

import ctypes
import ctypes.wintypes as wt
import re
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
FONT_DIR = ROOT / "runtime" / "SimpleGraphic" / "Fonts"

# Шрифты-доноры из ru/fonts (лицензия OFL), подключаются только для этого процесса
PRIVATE_FONT_DIR = ROOT / "ru" / "fonts"

# В Fontin нет кириллицы: русские буквы для него берутся из этого свободного шрифта.
# Переопределяется аргументом: python ru/tools/gen_fonts.py "Другой шрифт"
FONTIN_FACE = sys.argv[1] if len(sys.argv) > 1 else "PT Serif"

# Файл шрифта PoB -> донор кириллицы (GDI face, вес, курсив, моноширинный, капитель)
FONTS = {
	"Liberation Sans":          dict(face="Liberation Sans", weight=400),
	"Liberation Sans Bold":     dict(face="Liberation Sans", weight=700),
	"Bitstream Vera Sans Mono": dict(face="DejaVu Sans Mono", weight=400, mono=True),
	"Fontin":                   dict(face=FONTIN_FACE, weight=400),
	"Fontin Italic":            dict(face=FONTIN_FACE, weight=400, italic=True),
	"Fontin SmallCaps":         dict(face=FONTIN_FACE, weight=400, smallcaps=True),
	"Fontin SmallCaps Italic":  dict(face=FONTIN_FACE, weight=400, italic=True, smallcaps=True),
}

CODEPOINTS = (
	[0x0401, 0x0451]                     # Ё ё
	+ list(range(0x0410, 0x0450))        # А-я
	+ [0x00A0, 0x00AB, 0x00BB, 0x00B0, 0x00D7,   # nbsp « » ° ×
	   0x2013, 0x2014, 0x2026, 0x2116,           # – — … №
	   0x2018, 0x2019, 0x201C, 0x201D, 0x201E, 0x2212]  # ‘ ’ “ ” „ −
)

# ---------------------------------------------------------------- GDI

gdi32 = ctypes.WinDLL("gdi32")


class POINT(ctypes.Structure):
	_fields_ = [("x", wt.LONG), ("y", wt.LONG)]


class GLYPHMETRICS(ctypes.Structure):
	_fields_ = [("gmBlackBoxX", wt.UINT), ("gmBlackBoxY", wt.UINT),
		("gmptGlyphOrigin", POINT), ("gmCellIncX", ctypes.c_short), ("gmCellIncY", ctypes.c_short)]


class FIXED(ctypes.Structure):
	_fields_ = [("fract", wt.WORD), ("value", ctypes.c_short)]


class MAT2(ctypes.Structure):
	_fields_ = [("eM11", FIXED), ("eM12", FIXED), ("eM21", FIXED), ("eM22", FIXED)]


class TEXTMETRICW(ctypes.Structure):
	_fields_ = [(n, wt.LONG) for n in ("tmHeight", "tmAscent", "tmDescent", "tmInternalLeading",
		"tmExternalLeading", "tmAveCharWidth", "tmMaxCharWidth", "tmWeight", "tmOverhang",
		"tmDigitizedAspectX", "tmDigitizedAspectY")] + [(n, wt.WCHAR) for n in ("tmFirstChar",
		"tmLastChar", "tmDefaultChar", "tmBreakChar")] + [(n, wt.BYTE) for n in ("tmItalic",
		"tmUnderlined", "tmStruckOut", "tmPitchAndFamily", "tmCharSet")]


gdi32.CreateFontW.restype = wt.HFONT
gdi32.CreateFontW.argtypes = [ctypes.c_int] * 5 + [wt.DWORD] * 8 + [wt.LPCWSTR]
gdi32.CreateCompatibleDC.restype = wt.HDC
gdi32.CreateCompatibleDC.argtypes = [wt.HDC]
gdi32.SelectObject.restype = wt.HGDIOBJ
gdi32.SelectObject.argtypes = [wt.HDC, wt.HGDIOBJ]
gdi32.DeleteObject.argtypes = [wt.HGDIOBJ]
gdi32.GetGlyphOutlineW.restype = wt.DWORD
gdi32.GetGlyphOutlineW.argtypes = [wt.HDC, wt.UINT, wt.UINT, ctypes.POINTER(GLYPHMETRICS),
	wt.DWORD, ctypes.c_void_p, ctypes.POINTER(MAT2)]
gdi32.GetGlyphIndicesW.restype = wt.DWORD
gdi32.GetGlyphIndicesW.argtypes = [wt.HDC, wt.LPCWSTR, ctypes.c_int, ctypes.POINTER(wt.WORD), wt.DWORD]
gdi32.GetTextFaceW.argtypes = [wt.HDC, ctypes.c_int, wt.LPWSTR]

GGO_GRAY8_BITMAP = 6
GDI_ERROR = 0xFFFFFFFF
GGI_MARK_NONEXISTING_GLYPHS = 1
IDENTITY = MAT2(FIXED(0, 1), FIXED(0, 0), FIXED(0, 0), FIXED(0, 1))

HDC = gdi32.CreateCompatibleDC(None)

FR_PRIVATE = 0x10
gdi32.AddFontResourceExW.argtypes = [wt.LPCWSTR, wt.DWORD, ctypes.c_void_p]
for fontFile in sorted(PRIVATE_FONT_DIR.glob("*.ttf")):
	if not gdi32.AddFontResourceExW(str(fontFile), FR_PRIVATE, None):
		raise RuntimeError(f"Не удалось подключить шрифт {fontFile}")


class GdiFont:
	def __init__(self, face, size, weight=400, italic=False, mono=False):
		self.handle = gdi32.CreateFontW(size, 0, 0, 0, weight, int(italic), 0, 0, 1, 0, 0, 0,
			(1 if mono else 0) | 0x30, face)
		if not self.handle:
			raise RuntimeError(f"CreateFontW failed: {face} {size}")

	def __enter__(self):
		self.prev = gdi32.SelectObject(HDC, self.handle)
		buf = ctypes.create_unicode_buffer(64)
		gdi32.GetTextFaceW(HDC, 64, buf)
		self.actualFace = buf.value
		return self

	def __exit__(self, *exc):
		gdi32.SelectObject(HDC, self.prev)
		gdi32.DeleteObject(self.handle)

	@staticmethod
	def has(cp):
		idx = wt.WORD()
		gdi32.GetGlyphIndicesW(HDC, chr(cp), 1, ctypes.byref(idx), GGI_MARK_NONEXISTING_GLYPHS)
		return idx.value != 0xFFFF

	@staticmethod
	def glyph(cp):
		"""Возвращает (метрики, строки покрытия 0..255) для текущего шрифта DC."""
		gm = GLYPHMETRICS()
		size = gdi32.GetGlyphOutlineW(HDC, cp, GGO_GRAY8_BITMAP, ctypes.byref(gm), 0, None, ctypes.byref(IDENTITY))
		if size == GDI_ERROR:
			raise RuntimeError(f"GetGlyphOutlineW failed for U+{cp:04X}")
		rows = []
		if size:
			buf = (ctypes.c_ubyte * size)()
			gdi32.GetGlyphOutlineW(HDC, cp, GGO_GRAY8_BITMAP, ctypes.byref(gm), size, buf, ctypes.byref(IDENTITY))
			span = size // gm.gmBlackBoxY
			for y in range(gm.gmBlackBoxY):
				rows.append([min(255, round(buf[y * span + x] / 64 * 255)) for x in range(gm.gmBlackBoxX)])
		return gm, rows


def fit_size(cfg, targetCapH, guess, probe=ord("H")):
	"""Подбирает размер шрифта, при котором высота глифа probe равна targetCapH."""
	best = None
	for size in range(max(4, guess // 2), guess * 2 + 4):
		with GdiFont(cfg["face"], size, cfg["weight"], cfg.get("italic", False), cfg.get("mono", False)) as f:
			if best is None and f.actualFace != cfg["face"]:
				raise RuntimeError(f"Шрифт {cfg['face']!r} не найден (GDI подставил {f.actualFace!r})")
			gm, _ = f.glyph(probe)
		diff = abs(gm.gmBlackBoxY - targetCapH)
		key = (diff, abs(size - guess))
		if best is None or key < best[0]:
			best = (key, size)
	return best[1]

# ---------------------------------------------------------------- tgf / atlas

GLYPH_RE = re.compile(r"^GLYPH\s+(\d+)\s+(\d+)\s+(\d+)\s+(-?\d+)\s+(-?\d+);")


def parse_tgf(path):
	"""Список блоков [height, [строки GLYPH]]; строки CGLYPH отбрасываются."""
	blocks = []
	for line in path.read_text(encoding="utf-8").splitlines():
		m = re.match(r"^HEIGHT\s+(\d+);", line)
		if m:
			blocks.append([int(m.group(1)), []])
		elif line.startswith("GLYPH") and blocks:
			blocks[-1][1].append(line)
	return blocks


def glyph_rect(lines, cp):
	m = GLYPH_RE.match(lines[cp])
	x, y, w, sl, sr = map(int, m.groups())
	return x, y, w, sl, sr


def ink_rows(img, x, y, w, h):
	"""Первая и последняя строка ячейки глифа, где есть пиксели."""
	alpha = img.getchannel("A")
	rows = [r for r in range(h) if any(alpha.getpixel((x + c, y + r)) for c in range(w))]
	return rows[0], rows[-1]


def render_block(cfg, img, height, lines):
	"""Растеризует CODEPOINTS для одного размера; возвращает [(cp, rows, w, sl, sr)]."""
	hx, hy, hw, hsl, hsr = glyph_rect(lines, ord("H"))
	top, bottom = ink_rows(img, hx, hy, hw, height)
	baseline = bottom + 1
	capH = bottom - top + 1
	monoAdvance = hw + hsl + hsr

	size = fit_size(cfg, capH, height)
	variants = [(size, lambda cp: cp)]
	if cfg.get("smallcaps"):
		xx, xy, xw, _, _ = glyph_rect(lines, ord("x"))
		sTop, sBottom = ink_rows(img, xx, xy, xw, height)
		scSize = fit_size(cfg, sBottom - sTop + 1, height)
		variants.append((scSize, lambda cp: cp - 0x20 if 0x0430 <= cp <= 0x044F else 0x0401 if cp == 0x0451 else None))

	out = {}
	for vSize, mapCp in variants:
		with GdiFont(cfg["face"], vSize, cfg["weight"], cfg.get("italic", False), cfg.get("mono", False)) as f:
			for cp in CODEPOINTS:
				src = mapCp(cp)
				if src is None or not f.has(src):
					continue
				gm, rows = f.glyph(src)
				w = gm.gmBlackBoxX if rows else 0
				cell = [[0] * w for _ in range(height)]
				yo = baseline - gm.gmptGlyphOrigin.y
				for r, row in enumerate(rows):
					if 0 <= yo + r < height:
						cell[yo + r] = row
				sl = gm.gmptGlyphOrigin.x if rows else 0
				sr = gm.gmCellIncX - (sl + w)
				if cfg.get("mono"):
					sr = monoAdvance - (sl + w)
				out[cp] = (cell, w, sl, sr)
	return [(cp, *out[cp]) for cp in CODEPOINTS if cp in out]


def process_font(name, cfg):
	tgfPath = FONT_DIR / f"{name}.tgf"
	blocks = parse_tgf(tgfPath)
	tgf = []
	for height, lines in blocks:
		tgaPath = FONT_DIR / f"{name}.{height}.tga"
		img = Image.open(tgaPath).convert("RGBA")
		pad = height >> 2
		asciiBottom = max(glyph_rect(lines, i)[1] for i in range(len(lines))) + height + pad
		glyphs = render_block(cfg, img, height, lines)

		# Раскладка новых глифов под ASCII-областью
		width = img.width
		placed, x, y = [], 0, asciiBottom
		for cp, cell, w, sl, sr in glyphs:
			if x + w + pad > width:
				x, y = 0, y + height + pad
			placed.append((cp, x, y, cell, w, sl, sr))
			x += w + pad
		needH = y + height + pad
		newH = 1
		while newH < max(needH, asciiBottom):
			newH <<= 1

		atlas = Image.new("RGBA", (width, newH), (255, 255, 255, 0))
		atlas.paste(img.crop((0, 0, width, min(asciiBottom, img.height))), (0, 0))
		for cp, gx, gy, cell, w, sl, sr in placed:
			for r in range(height):
				for c in range(w):
					a = cell[r][c]
					if a:
						atlas.putpixel((gx + c, gy + r), (255, 255, 255, a))
		atlas.save(tgaPath, compression="tga_rle")

		tgf.append(f"HEIGHT {height};")
		tgf.extend(lines)
		for cp, gx, gy, cell, w, sl, sr in placed:
			tgf.append(f"CGLYPH {cp} {gx:3d} {gy:3d} {w:2d} {sl:2d} {sr:2d};\t// {chr(cp) if cp != 0xA0 else 'nbsp'}")
		print(f"  {name} {height}px: {len(placed)} глифов, атлас {width}x{img.height} -> {width}x{newH}")
	tgfPath.write_text("\n".join(tgf) + "\n", encoding="utf-8", newline="\r\n")


def main():
	for name, cfg in FONTS.items():
		print(name, "<-", cfg["face"])
		process_font(name, cfg)


if __name__ == "__main__":
	main()
