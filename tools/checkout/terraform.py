#!/usr/bin/env python3
"""Run Terraform in external working directories so atomic state writes survive clean."""
import os
from pathlib import Path
import shutil
import subprocess
import sys

os.umask(0o077)
repo=Path(__file__).resolve().parents[2]
state=Path(os.environ.get('SMARTHOME_STATE_DIR',Path.home()/'.local/share/smarthome')).expanduser().resolve()
if state==repo or repo in state.parents:
    raise SystemExit('Terraform state must be outside the checkout.')
args=sys.argv[1:]
if not args or args[0] not in ('-chdir=terraform/cloud','-chdir=terraform/storage'):
    raise SystemExit('Use the reviewed -chdir=terraform/cloud or -chdir=terraform/storage wrapper target.')
relative='usenet-infra/'+args[0].split('=',1)[1]
destination=state/'tree'/relative
if not (state/'manifest.json').is_file() or not destination.is_dir():
    raise SystemExit('External Terraform state is not provisioned; restore workstation state first.')
# Copy only tracked configuration, retaining private overrides and state.
paths=subprocess.check_output(['git','-C',str(repo),'ls-files','-z','--',relative]).split(b'\0')
for value in paths:
    if not value:continue
    name=os.fsdecode(value);source=repo/name
    if source.suffix!='.tf' and source.name!='.terraform.lock.hcl':continue
    target=destination/source.relative_to(repo/relative)
    if target.is_symlink():raise SystemExit('Refusing a symlinked external Terraform source.')
    target.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    shutil.copyfile(source,target)
args[0]='-chdir='+str(destination)
os.execvp(os.environ.get('TERRAFORM_BIN','terraform'),[os.environ.get('TERRAFORM_BIN','terraform'),*args])
