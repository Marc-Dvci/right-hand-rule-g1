"""Import the unchanged, vendored HIM builder kit."""
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
KIT = ROOT / 'vendor/builder-kit'
os.environ.setdefault('HIM_BALANCE_ONNX', str(ROOT / 'policy/models/balance.onnx'))
os.environ.setdefault('G1_SIM_THRASH_MODE', 'enforce')
for path in (KIT, KIT / 'robot_safety', KIT / 'containers/sim', KIT / 'packages/policy_safety/src'):
    sys.path.insert(0, str(path))

from runner import Runner  # noqa: E402
from plant import Plant  # noqa: E402
