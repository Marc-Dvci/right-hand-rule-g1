"""Optional report-export fix in an isolated kit copy; checker/plant unchanged."""
from pathlib import Path
import hashlib
import shutil


def prepare(root,report_timeout_fix=False):
    original = root/'vendor/builder-kit'
    if not report_timeout_fix:
        return original,None
    target = root/'execution/kit-report-timeout'
    if not target.exists():
        shutil.copytree(original,target,ignore=shutil.ignore_patterns('__pycache__','*.pyc','output','upload'))
    source = original/'containers/sim/bridge.py'
    before = source.read_text()
    needle = 'deadline = time.monotonic() + self.timeout'
    replacement = 'deadline = time.monotonic() + (max(self.timeout, 60.0) if request.get("op") == "report" else self.timeout)'
    if before.count(needle)!=1:
        raise ValueError('Public kit changed; review the report-timeout patch before applying')
    after = before.replace(needle,replacement)
    (target/'containers/sim/bridge.py').write_text(after)
    patch = dict(file='containers/sim/bridge.py',original_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                 patched_sha256=hashlib.sha256((target/'containers/sim/bridge.py').read_bytes()).hexdigest(),
                 before=needle,after=replacement,
                 scope='Only the report RPC timeout after simulation. Active control/freshness deadlines, dynamics, gains, safety checks and trace data are unchanged.')
    return target,patch
