"""Verify version-matched V2 source, frozen inventory and every packaged outcome."""
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import zipfile
import numpy as np
ROOT=Path(__file__).resolve().parents[1]


def main():
    # Also decode the entire film and check runner, secrets, ZIP and size limits.
    subprocess.run([sys.executable,str(ROOT/'tools/verify_package.py')],check=True)
    prefix='RightHandRule/'
    with zipfile.ZipFile(ROOT/'dist/RightHandRule.zip') as archive:
        inventory=json.loads(archive.read(prefix+'PACKAGE_INVENTORY.json'))['files']
        expected={prefix+r['path'] for r in inventory}|{prefix+'PACKAGE_INVENTORY.json'}
        if set(archive.namelist())!=expected:
            raise ValueError('Uninventoried package entry')
        frozen_bytes=archive.read(prefix+'evaluation/frozen-v2.json')
        frozen=json.loads(frozen_bytes)
        for name,digest in frozen['files'].items():
            if hashlib.sha256(archive.read(prefix+name)).hexdigest()!=digest:
                raise ValueError('Frozen packaged file changed: '+name)
        audit=json.loads(archive.read(prefix+'reports/v2/final-audit.json'))
        if hashlib.sha256(frozen_bytes).hexdigest()!=audit['freeze_sha256']:
            raise ValueError('Packaged evaluation freeze differs from final reports')
        if not audit['controls_complete'] or len(audit['rows'])!=480:
            raise ValueError('Incomplete final evidence')
        for row in audit['rows']:
            if hashlib.sha256(archive.read(prefix+row['report_path'])).hexdigest()!=row['report_sha256']:
                raise ValueError('Packaged final report changed')
        native=json.loads(archive.read(prefix+'reports/v2/native-summary.json'))
        image=json.loads(archive.read(prefix+'dist/image-provenance.json'))
        runner=json.loads(archive.read(prefix+'g1-runner.json'))
        if not native['exact_image_gate_passed'] or not native['image_sha256']==image['archive_sha256']==runner['image']['sha256']:
            raise ValueError('Exact-image qualification mismatch')
        for row in native['rows']:
            if hashlib.sha256(archive.read(prefix+row['report_path'])).hexdigest()!=row['report_sha256']:
                raise ValueError('Packaged native report changed')
        proof=json.loads(archive.read(prefix+'review/results/sensor-replay-v2-selected.json'))
        bundle=archive.read(prefix+'evidence/sensor-proof/v2-selected.npz')
        if hashlib.sha256(bundle).hexdigest()!=proof['bundle_sha256']:
            raise ValueError('Sensor proof bundle changed')
        with np.load(io.BytesIO(bundle),allow_pickle=False) as data:
            meta=json.loads(str(data['metadata']))
        if meta['controller_sha256']!=audit['controller_sha256'] or not proof['bitwise_numeric_match'] or proof['simulator_imported']:
            raise ValueError('Sensor proof is not version-matched')
        portable=json.loads(archive.read(prefix+'reports/v2/portable-motion-check.json'))
        if portable['episodes']!=480 or not portable['all_independent_scores_match']:
            raise ValueError('Portable motion audit incomplete')
        primitives=json.loads(archive.read(prefix+'reports/v2/primitive-summary.json'))
        if primitives['episodes']!=150 or len(primitives['rows'])!=150:
            raise ValueError('Supplemental primitives incomplete')
        for row in primitives['rows']:
            if hashlib.sha256(archive.read(prefix+row['report_path'])).hexdigest()!=row['report_sha256']:
                raise ValueError('Packaged primitive report changed')
    result=dict(frozen_files_match=True,complete_package_inventory=True,final_reports_verified=480,
        native_reports_verified=len(native['rows']),supplemental_reports_verified=150,exact_image_qualified=True,sensor_proof_version_matches=True,
        primary_gate_passed=audit['primary_gate_passed'],hardware_authorization=False)
    (ROOT/'dist/v2-package-check.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
    if not result['primary_gate_passed']:
        raise SystemExit('V2 declared primary gate is unmet; do not label the package fully qualified')


if __name__=='__main__':
    main()
