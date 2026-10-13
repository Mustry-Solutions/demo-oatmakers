"""Check that the generated demo resources still match tools/demo/build_views.py.

The demo views, page routes, session props and stylesheet are generated. This
check regenerates them and compares the result with what is committed, but
semantically: JSON files are compared as data, resource.json manifests without
the volatile lastModification metadata, and CSS without whitespace. A Designer
or gateway save that only reformats a file or restamps a manifest passes. A
real edit to a generated resource fails, because the next regeneration would
silently undo it.

Fix a failure in the generator: change tools/demo/build_views.py (or its
helpers), then run

    python3 tools/demo/build_views.py

and commit the regenerated files together with the generator change.

The check restores the working tree afterwards, so it is safe to run locally.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROJECT = 'projects/oatmakers'


def git(*args):
    return subprocess.run(['git', '-C', str(ROOT), *args], check=True,
                          capture_output=True, text=True).stdout


def normalize(path, data):
    if path.endswith('.json'):
        try:
            value = json.loads(data)
        except ValueError:
            return data
        if path.endswith('resource.json') and isinstance(value, dict):
            value = dict(value)
            attributes = dict(value.get('attributes') or {})
            attributes.pop('lastModification', None)
            attributes.pop('lastModificationSignature', None)
            value['attributes'] = attributes
        return value
    return re.sub(r'\s+', '', data)


def snapshot():
    files = git('ls-files', '-z', '--cached', '--others', '--exclude-standard', '--', PROJECT)
    return {name: (ROOT / name).read_bytes()
            for name in files.split('\0') if name and (ROOT / name).is_file()}


before = snapshot()
subprocess.run([sys.executable, str(ROOT / 'tools/demo/build_views.py')], check=True,
               cwd=ROOT, stdout=subprocess.DEVNULL)
after = snapshot()

problems = []
for name in sorted(set(before) | set(after)):
    old, new = before.get(name), after.get(name)
    if old == new:
        continue
    if old is None:
        problems.append(name + ': the generator creates it, but it is not in the repository')
    elif new is None:
        problems.append(name + ': the generator removes it, but it is still in the repository')
    elif normalize(name, old.decode('utf-8')) != normalize(name, new.decode('utf-8')):
        problems.append(name + ': differs from what the generator produces')

# Put the working tree back exactly as it was.
for name in set(after) - set(before):
    (ROOT / name).unlink()
for name, data in before.items():
    path = ROOT / name
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.is_file() or path.read_bytes() != data:
        path.write_bytes(data)

if problems:
    print('Generated demo resources were edited by hand:')
    for problem in problems:
        print('  ' + problem)
    print('Change tools/demo/build_views.py instead, run python3 tools/demo/build_views.py')
    print('and commit the regenerated files. See tools/demo/check_generated.py.')
    raise SystemExit(1)
print('Generated demo views, routes, session props and stylesheet match the generator.')
