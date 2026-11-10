"""Read Git metadata in native repositories and Windows-created WSL worktrees."""
import os
from pathlib import Path
import re
import subprocess
ROOT=Path(__file__).resolve().parents[1]


def command(*arguments):
    marker=ROOT/'.git'
    if marker.is_file():
        value=marker.read_text().strip().removeprefix('gitdir: ').strip()
        match=re.fullmatch(r'([A-Za-z]):[/\\](.*)',value)
        if os.name!='nt' and match:
            value='/mnt/'+match[1].lower()+'/'+match[2].replace('\\','/')
        directory=Path(value)
        if not directory.is_absolute():
            directory=(ROOT/directory).resolve()
        return ['git','--git-dir='+str(directory),'--work-tree='+str(ROOT),*arguments]
    return ['git','-C',str(ROOT),*arguments]


def read(*arguments):
    return subprocess.check_output(command(*arguments),cwd=ROOT)
