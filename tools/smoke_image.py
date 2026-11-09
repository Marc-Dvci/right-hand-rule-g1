from pathlib import Path
import subprocess
ROOT = Path(__file__).resolve().parents[1]
command = ['docker','run','--rm','--network','none','--entrypoint','python3',
           '--mount',f'type=bind,source={ROOT}/tools/container_smoke.py,target=/audit.py,readonly',
           'right-hand-rule:local','-u','/audit.py']
raise SystemExit(subprocess.run(command).returncode)
