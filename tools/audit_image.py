"""Compare the actual built ARM64 filesystem against the reviewed runtime source."""
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import tarfile

ROOT = Path(__file__).resolve().parents[1]
image = json.loads(subprocess.check_output(['docker','image','inspect','right-hand-rule:local']))[0]
if image['Architecture']!='arm64' or image['Os']!='linux':
    raise SystemExit('Wrong image platform')
container_id = subprocess.check_output(['docker','create','--platform','linux/arm64','right-hand-rule:local']).decode().strip()
records = []
try:
    with tempfile.TemporaryDirectory(prefix='rhr-image-') as directory:
        target = Path(directory)/'submission'
        subprocess.run(['docker','cp',container_id+':/submission',str(target)],check=True)
        sources = {p:p.relative_to(ROOT).as_posix() for p in (ROOT/'policy').rglob('*')
                   if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.onnx'}
        for name in ('ros_node.py','timing.py','entrypoint.sh'):
            sources[ROOT/'container'/name] = name
        for name in ('navigation','control','deployment'):
            sources[ROOT/f'config/{name}.json'] = 'config/'+name+'.json'
        for source,destination in sorted(sources.items()):
            expected = hashlib.sha256(source.read_bytes()).hexdigest()
            actual = hashlib.sha256((target/destination).read_bytes()).hexdigest()
            if expected != actual:
                raise ValueError('Image/source mismatch: '+destination)
            records.append(dict(source=source.relative_to(ROOT).as_posix(),image_path='/submission/'+destination,sha256=actual))
finally:
    subprocess.run(['docker','rm',container_id],check=True,stdout=subprocess.DEVNULL)
report = dict(image_id=image['Id'],platform='linux/arm64',files=records,all_match=True,
              intentional_exclusions='ONNX originals remain in source for parity; NumPy exports are the runtime models.')
archive=ROOT/'dist/submission.tar'
with tarfile.open(archive) as tar:
    manifest=json.load(tar.extractfile('manifest.json'))
    config=tar.extractfile(manifest[0]['Config']).read()
report['archive_config_digest']='sha256:'+hashlib.sha256(config).hexdigest()
digest=hashlib.sha256()
with archive.open('rb') as stream:
    for chunk in iter(lambda:stream.read(1024*1024),b''):
        digest.update(chunk)
report['archive_sha256']=digest.hexdigest()
report['identity_note']='Docker containerd storage reports the OCI manifest ID locally; classic overlay2 reports the config ID on the native runner. Archive SHA-256 is the cross-engine exact-byte identity.'
(ROOT/'dist/image-provenance.json').write_text(json.dumps(report,indent=2)+'\n')
print('Exact image/source match:',len(records),'files;',image['Id'])
