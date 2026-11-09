"""Temporary ARM interpreter override; always restore the original registration."""
from pathlib import Path
import hashlib
import json
import os
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = Path('/proc/sys/fs/binfmt_misc')
ENTRY = REGISTRY/'qemu-aarch64'
QEMU = Path(os.environ.get('QEMU_AARCH64',str(ROOT/'.tools/qemu-aarch64')))


def register(fields, interpreter, flags):
    def escaped(value):
        return ''.join('\\x'+value[i:i+2] for i in range(0,len(value),2))
    if ENTRY.exists():
        ENTRY.write_text('-1')
    definition = f':qemu-aarch64:M:{fields["offset"]}:{escaped(fields["magic"])}:{escaped(fields["mask"])}:{interpreter}:{flags}'
    (REGISTRY/'register').write_bytes(definition.encode())


def main():
    if os.geteuid()!=0:
        raise RuntimeError('This wrapper needs root only to change binfmt; the kit runs as dev.')
    running = subprocess.check_output(['docker','ps','-q'],text=True).split()
    for container in running:
        metadata = json.loads(subprocess.check_output(['docker','inspect',container],text=True))[0]
        image = json.loads(subprocess.check_output(['docker','image','inspect',metadata['Image']],text=True))[0]
        if image['Architecture']=='arm64':
            raise RuntimeError('Do not switch an interpreter while another ARM64 container runs')
    original = ENTRY.read_text()
    fields = {line.split(' ',1)[0]:line.split(' ',1)[1] for line in original.splitlines() if ' ' in line}
    fields['flags'] = next(line.split(':',1)[1].strip() for line in original.splitlines() if line.startswith('flags:'))
    if not QEMU.is_file():
        raise RuntimeError('Missing previously installed QEMU 10.2.3 binary')
    (ROOT/'research/qemu-before.txt').write_text(original)
    try:
        register(fields,str(QEMU),'CFP')
        print('Temporary ARM64 emulator:',subprocess.check_output([str(QEMU),'--version'],text=True).splitlines()[0],flush=True)
        result = subprocess.run(['runuser','-u','dev','--',sys.executable,str(ROOT/'tools/run_kit.py'),*sys.argv[1:]])
        return result.returncode
    finally:
        try:
            inspected = subprocess.run(['docker','inspect','g1-desktop-sim-submission-1'],capture_output=True,text=True)
            if inspected.returncode==0:
                data = json.loads(inspected.stdout)[0]
                if data['State']['Running'] and data['Config']['Image']=='right-hand-rule:local':
                    subprocess.run(['docker','stop','-t','2','g1-desktop-sim-submission-1'],check=True)
        finally:
            register(fields,fields['interpreter'],fields['flags'])
            assert fields['interpreter'] in ENTRY.read_text()
            print('Original ARM64 interpreter restored',flush=True)


if __name__=='__main__':
    raise SystemExit(main())
