"""Run the built ARM64 image with the original kit, preserving raw evidence."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import hashlib
import platform

ROOT = Path(__file__).resolve().parents[1]
KIT = ROOT/'vendor/builder-kit'
p = argparse.ArgumentParser()
p.add_argument('--scene', default='standard')
p.add_argument('--seconds', type=int, default=60)
p.add_argument('--name', default='standard-001')
p.add_argument('--counterfactuals', action='store_true')
p.add_argument('--report-timeout-fix',action='store_true')
args = p.parse_args()
if not args.name or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-' for c in args.name):
    raise ValueError('Use a simple unique evidence name')
native = platform.machine().lower() in ('aarch64','arm64')
output = ROOT/'evidence'/('container-native' if native else 'container-qemu')/args.name
if output.exists() and any(output.iterdir()):
    raise SystemExit('Refusing to replace existing native evidence: '+str(output))
from prepare_kit import prepare
KIT,patch = prepare(ROOT,args.report_timeout_fix)
environment = KIT/'containers/upload/environment'
shutil.copytree(ROOT/'scene', environment, dirs_exist_ok=True)
output.mkdir(parents=True, exist_ok=True)
command = ['bash','sim.sh','--image','right-hand-rule:local','--seconds',str(args.seconds),'--output',str(output)]
if args.scene != 'standard':
    command.extend(['--scene',f'containers/upload/environment/{args.scene}.xml'])
if args.counterfactuals:
    command.append('--counterfactuals')
image = json.loads(subprocess.check_output(['docker','image','inspect','right-hand-rule:local'],text=True))[0]
archive = ROOT/'dist/submission.tar'
archive_digest = None
if archive.exists():
    digest = hashlib.sha256()
    with archive.open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):
            digest.update(chunk)
    archive_digest = digest.hexdigest()
(output/'invocation.json').write_text(json.dumps(dict(command=command,image_id=image['Id'],
    image_architecture=image['Architecture'],image_archive_sha256=archive_digest,
    report_timeout_patch=patch,
    runtime='native ARM64' if native else 'local x86_64 with ARM64 emulation; not native ARM64',
    github_run=(os.environ.get('GITHUB_SERVER_URL','https://github.com')+'/'+os.environ['GITHUB_REPOSITORY']+'/actions/runs/'+os.environ['GITHUB_RUN_ID'])
        if os.environ.get('GITHUB_REPOSITORY') and os.environ.get('GITHUB_RUN_ID') else None),indent=2)+'\n')
with (output/'launcher.log').open('w') as log:
    result = subprocess.run(command,cwd=KIT,env=dict(os.environ,DOCKER_BUILDKIT='0'),stdout=log,stderr=log)
print('kit exit',result.returncode,'evidence',output,flush=True)
if (output/'builder-check.json').exists():
    print((output/'builder-check.json').read_text(),flush=True)
else:
    print((output/'launcher.log').read_text()[-5000:],flush=True)
raise SystemExit(result.returncode)
