"""Create an updated reading copy without rewriting any signed source files."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from automator.evidence import sha256_file
from automator.report import report_html


def create_reading_copy(folder):
    folder = Path(folder).resolve()
    manifest = folder / 'hashes.sha256'
    listed = {}
    for line in manifest.read_text(encoding='utf-8').splitlines():
        digest, name = line.split(' *', 1)
        target = (folder / name).resolve()
        if not target.is_relative_to(folder) or sha256_file(target) != digest:
            raise ValueError(f'Originaldatei stimmt nicht mit der Hashliste überein: {name}')
        listed[name] = digest
    manifest_hash = sha256_file(manifest)
    target = folder / 'bericht-lesefassung.html'
    if target.name in listed:
        raise ValueError('Die Lesefassung ist bereits Teil der Original-Hashliste und wird nicht überschrieben.')
    record = json.loads((folder / 'sicherung.json').read_text(encoding='utf-8'))
    target.write_text(report_html(record, original_report='bericht.html'), encoding='utf-8')
    # Explicit checks instead of assert: they must also run under python -O.
    if sha256_file(manifest) != manifest_hash or any(sha256_file(folder / name) != digest for name, digest in listed.items()):
        raise ValueError('Originaldateien haben sich beim Erstellen der Lesefassung verändert.')
    return target


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Separate Lesefassung einer bestehenden Sicherung erstellen.')
    parser.add_argument('folder', type=Path)
    args = parser.parse_args()
    print(create_reading_copy(args.folder))
