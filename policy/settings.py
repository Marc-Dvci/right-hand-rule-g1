"""One configuration source for direct API, evaluator and installed ROS runner."""
import json
from pathlib import Path

CONFIG = Path(__file__).resolve().parents[1] / 'config'


def load_settings(name):
    if name not in ('navigation', 'control', 'deployment'):
        raise ValueError('Unknown policy configuration')
    # A missing deployment file is an error, never a silent change of controller.
    value = json.loads((CONFIG / (name + '.json')).read_text())
    if not isinstance(value, dict):
        raise ValueError('Policy configuration must be a JSON object')
    return value
