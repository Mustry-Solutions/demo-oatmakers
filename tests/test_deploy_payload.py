"""The production deploy ships exactly what release.yaml pins, from the tags.

Runs the real "Parse release.yaml" and "Assemble the payload from the pinned
tags" steps of .github/workflows/deploy.yml against a throwaway repository.
Needs git, bash and PyYAML.
"""
from pathlib import Path
import os
import subprocess
import tempfile

import yaml

ROOT = Path(__file__).resolve().parents[1]
workflow = yaml.safe_load((ROOT / '.github/workflows/deploy.yml').read_text())
steps = {step.get('name'): step for step in workflow['jobs']['deploy']['steps']}
PARSE = steps['Parse release.yaml']['run']
ASSEMBLE = steps['Assemble the payload from the pinned tags']['run']

with tempfile.TemporaryDirectory() as temporary:
    repo = Path(temporary) / 'repo'
    runner_temp = Path(temporary) / 'runner-temp'
    repo.mkdir()
    runner_temp.mkdir()

    def git(*args):
        return subprocess.check_output(['git', '-C', str(repo), *args], text=True)

    def write(name, text):
        path = repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)

    def run(script, check=True):
        env = {**os.environ, 'RUNNER_TEMP': str(runner_temp), 'SITE': 'oatmakers-site-7'}
        return subprocess.run(['bash', '-c', script], cwd=repo, env=env, check=check,
                              capture_output=True, text=True)

    git('init', '-q')
    git('config', 'user.email', 'test@example.com')
    git('config', 'user.name', 'Payload Test')

    # oatmakers@v5.0.0 carries the gateway-level payload.
    write('projects/oatmakers/project.json', 'oatmakers v5.0.0')
    write('services/config/resources/core/ignition/database-connection/OatmakersDemo/config.json', 'db v5.0.0')
    write('services/config/resources/core/ignition/system-properties/config.json', 'local identity')
    write('services/modules.json', 'manifest v5.0.0')
    write('third-party-modules/UI.modl', 'module')
    write('jar-files/jar/lib.jar', 'jar')
    write('db-migration/migrate/000001_demo.up.sql', 'up')
    write('db-migration/migrate/000001_demo.down.sql', 'down')
    git('add', '.')
    git('commit', '-qm', 'oatmakers v5.0.0')
    git('tag', 'oatmakers@v5.0.0')

    # A student project, tagged later, while main moves on.
    write('projects/wout/project.json', 'wout v1.0.0')
    git('add', '.')
    git('commit', '-qm', 'wout v1.0.0')
    git('tag', 'wout@v1.0.0')

    # Work on main after the tags must not ship, and neither may an unpinned
    # project or an uncommitted edit.
    write('projects/oatmakers/project.json', 'oatmakers untagged')
    write('services/modules.json', 'manifest untagged')
    write('projects/stephan/project.json', 'not pinned')
    git('add', '.')
    git('commit', '-qm', 'later work')
    # The checkout's view of main: every pinned tag must sit on it.
    git('update-ref', 'refs/remotes/origin/main', 'HEAD')

    # A tag on a branch that never merged.
    git('switch', '-qc', 'unmerged')
    write('projects/wout/project.json', 'wout unreviewed')
    git('add', 'projects/wout/project.json')
    git('commit', '-qm', 'unreviewed work')
    git('tag', 'wout@v1.1.0')
    git('switch', '-q', '-')
    write('projects/wout/project.json', 'dirty local edit')

    write('release.yaml', 'gateway: oatmakers-site-7\nprojects:\n  oatmakers: v5.0.0   # shared\n  wout: v1.0.0\n')
    run(PARSE)
    run(ASSEMBLE)
    payload = repo / 'payload'
    assert (payload / 'projects/oatmakers/project.json').read_text() == 'oatmakers v5.0.0'
    assert (payload / 'projects/wout/project.json').read_text() == 'wout v1.0.0'
    assert not (payload / 'projects/stephan').exists(), 'an unpinned project shipped'
    assert (payload / 'services/modules.json').read_text() == 'manifest v5.0.0'
    assert (payload / 'services/config/resources/core/ignition/database-connection/OatmakersDemo/config.json').exists()
    assert not (payload / 'services/config/resources/core/ignition/system-properties').exists(), 'gateway identity shipped'
    assert (payload / 'third-party-modules/UI.modl').exists()
    assert (payload / 'jar-files/jar/lib.jar').exists()
    assert (payload / 'db-migration/migrate/000001_demo.up.sql').exists()
    print('PASS pinned projects ship from their tags; gateway payload rides the oatmakers tag')

    # Removing a pin removes the project from the payload (and the wipe-then-copy
    # deploy removes it from the gateway).
    write('release.yaml', 'gateway: oatmakers-site-7\nprojects:\n  oatmakers: v5.0.0\n')
    run(PARSE)
    run(ASSEMBLE)
    assert not (payload / 'projects/wout').exists()
    print('PASS an unpinned project leaves the payload')

    # Refusals.
    for release, reason in [
        ('gateway: oatmakers-site-7\nprojects:\n  oatmakers: v5.0.0\n  wout: v9.9.9\n', 'tag does not exist'),
        ('gateway: oatmakers-site-7\nprojects:\n  oatmakers: v5.0.0\n  wout: v1.1.0\n', 'a tag that is not on main'),
        ('gateway: oatmakers-site-7\nprojects:\n  wout: v1.0.0\n', 'oatmakers pin missing'),
        ('gateway: somewhere-else\nprojects:\n  oatmakers: v5.0.0\n', 'wrong gateway'),
        ('gateway: oatmakers-site-7\nprojects:\n  oatmakers: 5.0\n', 'unparsable version'),
    ]:
        write('release.yaml', release)
        result = run(PARSE + '\n' + ASSEMBLE, check=False)
        assert result.returncode != 0, 'accepted a release with ' + reason
        if reason == 'a tag that is not on main':
            assert 'not on main' in result.stderr, result.stderr
    print('PASS missing tags, tags off main, a missing oatmakers pin, another gateway and bad versions are refused')
