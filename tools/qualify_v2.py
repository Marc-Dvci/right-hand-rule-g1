"""Path-normalizing CLI for the unchanged, pre-holdout frozen V2 auditor."""
import argparse
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools.audit_v2 import audit


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('directories',nargs='+',type=Path)
    p.add_argument('--output',type=Path,default=ROOT/'reports/v2/final-audit.json')
    p.add_argument('--primary-only',action='store_true')
    a=p.parse_args()
    result=audit([d.resolve() for d in a.directories],a.output.resolve(),require_controls=not a.primary_only)
    print(json.dumps({k:v for k,v in result.items() if k!='rows'},indent=2))
    raise SystemExit(0 if result['primary_gate_passed'] else 2)
