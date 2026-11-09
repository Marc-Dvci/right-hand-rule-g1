"""Audit the exact git inventory before the user-authorized publication."""
from pathlib import Path
import hashlib
import json
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
files = subprocess.check_output(['git','ls-files','-z'],cwd=ROOT).decode().split('\0')
patterns = [rb'github_pat_[A-Za-z0-9_]{30,}',rb'gh[pousr]_[A-Za-z0-9]{25,}',
            rb'sk-[A-Za-z0-9]{30,}',rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----']
blocked,inventory = [],[]
for name in filter(None,files):
    path = ROOT/name
    data = path.read_bytes()
    if any(part in ('.venv','.aws','.ssh','credentials.json','.env') for part in path.relative_to(ROOT).parts):
        blocked.append(name)
    if any(re.search(pattern,data) for pattern in patterns):
        blocked.append(name)
    inventory.append(dict(path=name,bytes=len(data),sha256=hashlib.sha256(data).hexdigest()))
report = dict(files=len(inventory),bytes=sum(row['bytes'] for row in inventory),blocked=blocked,inventory=inventory)
output = ROOT/'research/publication-audit.json'
output.write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k!='inventory'},indent=2))
if blocked:
    raise SystemExit('Do not publish: blocked inventory')
