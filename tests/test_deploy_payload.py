"""A deployment ships the commit and only resources owned by Oatmakers."""
from pathlib import Path
import os
import subprocess
import tempfile

SCRIPT = Path(__file__).resolve().parents[1] / 'ops/assemble-deploy.sh'
with tempfile.TemporaryDirectory() as temporary:
    repo = Path(temporary) / 'repo'
    repo.mkdir()
    def git(*args):
        return subprocess.check_output(['git', '-C', str(repo), *args], text=True)
    git('init', '-q')
    git('config', 'user.email', 'test@example.com')
    git('config', 'user.name', 'Payload Test')
    paths = [
        'projects/oatmakers/project.json',
        'services/ignition/config/resources/core/ignition/database-connection/OatmakersDemo/config.json',
        'services/ignition/config/resources/core/ignition/secret-provider/DemoRuntime/config.json',
        'db-migration/migrate/000001_demo.up.sql',
        'services/ignition/third-party-modules/UI.modl',
        'tools/demo/mustry-ui-version.json',
        'services/ignition/config/resources/core/ignition/user-source/default/config.json',
        'services/ignition/config/resources/core/ignition/api-token/private/config.json',
        'services/ignition/config/resources/core/ignition/system-properties/config.json',
    ]
    for name in paths:
        p = repo / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text('committed')
    git('add', '.')
    git('commit', '-qm', 'Committed resources')
    (repo / 'projects/oatmakers/project.json').write_text('dirty local edit')
    output = Path(temporary) / 'payload'
    subprocess.run(['bash', str(SCRIPT), str(output)], cwd=repo, check=True,
                   env={**os.environ, 'GITHUB_SHA': git('rev-parse', 'HEAD').strip()})
    assert (output / 'projects/oatmakers/project.json').read_text() == 'committed'
    assert not (output / 'services/ignition/config/resources/core/ignition/user-source').exists()
    assert not (output / 'services/ignition/config/resources/core/ignition/api-token').exists()
    assert not (output / 'services/ignition/config/resources/core/ignition/system-properties').exists()
    assert (output / 'db-migration/migrate/000001_demo.up.sql').exists()
    assert (output / 'services/ignition/config/resources/core/ignition/database-connection/OatmakersDemo/config.json').exists()
print('PASS committed demo ships with migrations; gateway credentials and identity stay out')
