"""Готовит релиз русской версии: манифест для встроенного апдейтера, пакет и портативный ZIP.

1. Пересчитывает manifest.xml в корне репозитория (update_manifest.py из PoB) и направляет
   источники обновлений на этот форк: ветку release репозитория --repo.
2. Раскладывает файлы так, как их раскладывает установка PoB (всё в одну папку), в <out>/pkg;
   в manifest.xml пакета прописаны ветка release и платформа, поэтому программа не уходит
   в режим разработчика и сама скачивает обновления.
3. Упаковывает портативный ZIP.

Запуск: python ru/tools/make_release.py --version 2.67.2-ru.1 [--repo owner/name] [--out dist]
"""

import argparse
import shutil
import sys
import xml.etree.ElementTree as Et
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
UPSTREAM_URL = "https://raw.githubusercontent.com/PathOfBuildingCommunity/PathOfBuilding/{branch}/"
BRANCH = "release"

# Файлы runtime, которых нет в манифесте (апдейтер их не обновляет), но без которых нет установки
RUNTIME_EXTRA = ["Update.exe", "msvcr100.dll"]
PART_DIRS = {"default": ROOT, "runtime": ROOT / "runtime", "program": ROOT / "src", "tree": ROOT / "src"}


def build_manifest(version, repo):
	sys.path.insert(0, str(ROOT))
	import update_manifest
	update_manifest.create_manifest(version, replace=True)
	manifest = ROOT / "manifest.xml"
	text = manifest.read_text(encoding="utf-8")
	manifest.write_text(text.replace(UPSTREAM_URL, f"https://raw.githubusercontent.com/{repo}/{{branch}}/"), encoding="utf-8")
	return manifest


def build_package(manifest, out):
	pkg = out / "pkg"
	if pkg.exists():
		shutil.rmtree(pkg)
	pkg.mkdir(parents=True)
	tree = Et.parse(manifest)
	count = 0
	for node in tree.getroot().iter("File"):
		src = PART_DIRS[node.get("part")] / node.get("name")
		dst = pkg / node.get("name")
		dst.parent.mkdir(parents=True, exist_ok=True)
		shutil.copy2(src, dst)
		count += 1
	for name in RUNTIME_EXTRA:
		shutil.copy2(ROOT / "runtime" / name, pkg / name)
	# Манифест установленной копии: ветка и платформа, по ним апдейтер ищет обновления
	version = tree.getroot().find("Version")
	version.set("branch", BRANCH)
	version.set("platform", "win32")
	tree.write(pkg / "manifest.xml", encoding="UTF-8", xml_declaration=True)
	return pkg, count


def build_zip(pkg, out, version):
	path = out / f"PathOfBuilding-RU-{version}-portable.zip"
	with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
		for file in sorted(pkg.rglob("*")):
			if file.is_file():
				zf.write(file, Path("Path of Building RU") / file.relative_to(pkg))
	return path


def main():
	parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
	parser.add_argument("--version", required=True)
	parser.add_argument("--repo", default="panchishen/PathOfBuilding-RU")
	parser.add_argument("--out", default=str(ROOT / "ru" / "dist"))
	args = parser.parse_args()
	out = Path(args.out)
	manifest = build_manifest(args.version, args.repo)
	pkg, count = build_package(manifest, out)
	zipPath = build_zip(pkg, out, args.version)
	print(f"Версия {args.version}: файлов в пакете {count}, ZIP {zipPath.name} ({zipPath.stat().st_size // 1024 // 1024} МБ)")


if __name__ == "__main__":
	main()
