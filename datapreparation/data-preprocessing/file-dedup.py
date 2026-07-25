from pathlib import Path
import os
import re


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data" / "nse_files"
DEST = ROOT / "data" / "nse_files_final"
HASH_SUFFIX = re.compile(r"_[0-9a-fA-F]{8,}$")


def original_name_for_hash_file(path):
    original_stem = HASH_SUFFIX.sub("", path.stem)
    if original_stem == path.stem:
        return None
    return original_stem + path.suffix


def main():
    for folder in ("keep", "review"):
        src_dir = SOURCE / folder
        dest_dir = DEST / folder
        dest_dir.mkdir(parents=True, exist_ok=True)

        for old_file in dest_dir.iterdir():
            if old_file.is_file():
                old_file.unlink()

        source_files = [path for path in src_dir.iterdir() if path.is_file()]
        source_names = {path.name for path in source_files}

        for path in source_files:
            original_name = original_name_for_hash_file(path)
            if original_name in source_names:
                continue

            dest_path = dest_dir / path.name
            os.link(path, dest_path)


if __name__ == "__main__":
    main()
