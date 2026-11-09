import hashlib
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from prepare_kit import prepare


def test_report_fix_is_isolated_and_preserves_active_checks(tmp_path):
    original = tmp_path/'vendor/builder-kit'
    (original/'containers/sim').mkdir(parents=True)
    (original/'robot_safety').mkdir()
    source = original/'containers/sim/bridge.py'
    before = 'deadline = time.monotonic() + self.timeout\n'
    source.write_text(before)
    (original/'robot_safety/core.py').write_text('active_deadline = 0.2\n')
    (original/'containers/sim/plant.py').write_text('PHYSICS_DT = 0.002\n')
    target,patch = prepare(tmp_path,True)
    assert source.read_text()==before
    assert patch['original_sha256']==hashlib.sha256(source.read_bytes()).hexdigest()
    assert 'request.get("op") == "report"' in (target/'containers/sim/bridge.py').read_text()
    for name in ('robot_safety/core.py','containers/sim/plant.py'):
        assert (target/name).read_bytes()==(original/name).read_bytes()
