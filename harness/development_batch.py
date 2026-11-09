"""Use isolated processes; native simulator memory is released per episode."""
from pathlib import Path
import subprocess
import sys
ROOT = Path(__file__).resolve().parents[1]
for scene, seconds, suffix in [('inner',100,'inner-001-mj337'), ('outer',100,'outer-005-mj337'), ('flat',60,'flat-001-mj337')]:
    subprocess.run([sys.executable, str(ROOT/'harness/evaluate.py'), '--scene', scene,
                    '--seconds', str(seconds), '--output', str(ROOT/'evidence/development'/suffix)], check=True)
