"""Verify the final contest ZIP, runner reference, size limits and video decode."""
import hashlib
import json
from pathlib import Path,PurePosixPath
import re
import subprocess
import zipfile
import imageio_ffmpeg

ROOT=Path(__file__).resolve().parents[1]
dist=ROOT/'dist'
package=dist/'RightHandRule.zip'
video=dist/'result.mp4'
blocked=[]
patterns=[rb'github_pat_[A-Za-z0-9_]{30,}',rb'gh[pousr]_[A-Za-z0-9]{25,}',
          rb'sk-[A-Za-z0-9]{30,}',rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----']
with zipfile.ZipFile(package) as archive:
    assert archive.testzip() is None
    names=archive.namelist()
    assert len(names)==len(set(names))
    for name in names:
        path=PurePosixPath(name)
        assert not path.is_absolute() and '..' not in path.parts and path.parts[0]=='RightHandRule'
        assert not any(part in ('.git','.venv','.aws','.ssh','.env','credentials.json') for part in path.parts)
        if any(re.search(pattern,archive.read(name)) for pattern in patterns):
            blocked.append(name)
    assert not blocked,blocked
    inventory=json.loads(archive.read('RightHandRule/PACKAGE_INVENTORY.json'))
    for row in inventory['files']:
        data=archive.read('RightHandRule/'+row['path'])
        assert len(data)==row['bytes'] and hashlib.sha256(data).hexdigest()==row['sha256']
    runner=json.loads(archive.read('RightHandRule/g1-runner.json'))
    assert runner['required_sensors']==['joint_state','imu']
    assert runner['image']['sha256']==json.loads((dist/'image-provenance.json').read_text())['archive_sha256']
    assert runner['repository_commit']=='e93c49267a7b6b905c6666c8c70668f8ee7ac397'
    assert 'RightHandRule/arena-policy.json' not in names
    assert archive.getinfo('RightHandRule/run.sh').external_attr>>16 & 0o111
    assert sum(name.endswith('/g1-runner.json') for name in names)==1
ffmpeg=imageio_ffmpeg.get_ffmpeg_exe()
probe=subprocess.run([ffmpeg,'-hide_banner','-i',str(video)],capture_output=True,text=True)
duration=re.search(r'Duration: (\d+):(\d+):(\d+\.\d+)',probe.stderr)
assert duration
seconds=int(duration[1])*3600+int(duration[2])*60+float(duration[3])
assert 81.9<=seconds<=82.1 and '1280x720' in probe.stderr and '24 fps' in probe.stderr
subprocess.run([ffmpeg,'-v','error','-i',str(video),'-f','null','-'],check=True,capture_output=True)
assert video.stat().st_size<=50_000_000
assert package.stat().st_size+video.stat().st_size<=100_000_000
result=dict(zip_integrity=True,all_inventory_digests_match=True,blocked_files=blocked,
    unique_runner_reference=True,runner_reference_matches_tested_image=True,executable_run_script=True,
    video_decodes=True,video_seconds=seconds,video_bytes=video.stat().st_size,
    contest_zip_bytes=package.stat().st_size,combined_bytes=package.stat().st_size+video.stat().st_size,
    contest_size_limits_met=True)
(dist/'package-check.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
