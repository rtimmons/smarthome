#!/usr/bin/env python3
"""Prove the NAS reader cannot modify a disposable, writer-owned sentinel.

Only one UUID-named file under catalog/.acceptance is created and removed.
Remote keys remain on their hosts; no raw diagnostics or configuration escape.
Run with the existing CLOUD_SSH_* and QNAP_SSH_* variables loaded by just.
"""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import shlex
import subprocess
import uuid

SPEC = importlib.util.spec_from_file_location('qnap_recon', Path(__file__).with_name('qnap-recon.py'))
assert SPEC and SPEC.loader
recon = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(recon)

WRITER = r'''
import hashlib,json,re,subprocess,sys
try:
 action,token,*receipt=sys.argv[1:]
 assert action in ("create","finish") and re.fullmatch(r"[0-9a-f]{32}",token)
 remote="storagebox:catalog/.acceptance/reader-"+token+".txt"
 original=("usenet reader acceptance "+token+"\n").encode()
 prefix=["rclone","--config","/srv/usenet/config/rclone/rclone.conf","--contimeout","10s","--timeout","15s","--retries","1","--low-level-retries","1"]
 def run(*args,data=None):
  return subprocess.run(prefix+list(args),input=data,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=30)
 def absent(result):
  return result.returncode!=0 and any(x in result.stderr.lower() for x in (b"object not found",b"directory not found",b"no such file",b"does not exist"))
 current=run("cat",remote)
 if action=="create":
  assert absent(current),"sentinel_path_not_confirmed_absent"
  written=run("rcat",remote,"--immutable",data=original)
  assert written.returncode==0
  check=run("cat",remote)
  assert check.returncode==0 and check.stdout==original
  result={"created":True,"sha256":hashlib.sha256(original).hexdigest()}
 else:
  preserved=current.returncode==0 and hashlib.sha256(current.stdout).digest()==hashlib.sha256(original).digest()
  if absent(current):
   cleaned=True
  else:
   assert preserved or receipt==["created"],"refuse_cleanup_without_ownership_receipt"
   removed=run("deletefile",remote)
   cleaned=removed.returncode==0 and absent(run("cat",remote))
  result={"original_preserved":preserved,"cleaned":cleaned}
 print(json.dumps(result))
except Exception:
 print(json.dumps({"error":"private_writer_probe_failed"}))
 sys.exit(1)
'''

READER = r'''
import json,re,subprocess,sys
try:
 token=sys.argv[1]
 assert re.fullmatch(r"[0-9a-f]{32}",token)
 remote="storagebox:.acceptance/reader-"+token+".txt"
 original=("usenet reader acceptance "+token+"\n").encode()
 prefix=["rclone","--contimeout","10s","--timeout","15s","--retries","1","--low-level-retries","1"]
 def run(*args,data=None):
  return subprocess.run(prefix+list(args),input=data,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=30)
 def denied(result):
  # This Storage Box returns generic SSH_FX_FAILURE for prohibited writes.
  # Require an explicit SFTP server rejection; transport errors never pass.
  return result.returncode!=0 and any(x in result.stderr.lower() for x in (b"permission denied",b"operation not permitted",b"ssh_fx_permission_denied",b"ssh_fx_failure"))
 def diagnostic(result):
  error=result.stderr.lower()
  return {"exit_code":result.returncode,"sftp_permission_denied":b"ssh_fx_permission_denied" in error,
          "sftp_failure":b"ssh_fx_failure" in error,"permission_denied":b"permission denied" in error,
          "read_only":b"read-only" in error or b"read only" in error,
          "unsupported":b"not supported" in error or b"unsupported" in error,
          "connection_failure":b"connection" in error or b"eof" in error,
          "generic_failure":b"failure" in error,"unknown_argument":b"unknown flag" in error}
 before=run("cat",remote)
 assert before.returncode==0 and before.stdout==original
 overwrite=run("rcat",remote,data=b"disposable reader overwrite test\n")
 after_overwrite=run("cat",remote)
 delete=run("deletefile",remote)
 after_delete=run("cat",remote)
 print(json.dumps({"read_matched":True,"overwrite_denied":denied(overwrite),"delete_denied":denied(delete),
                   "overwrite_diagnostic":diagnostic(overwrite),"delete_diagnostic":diagnostic(delete),
                   "preserved_after_overwrite":after_overwrite.returncode==0 and after_overwrite.stdout==original,
                   "preserved_after_delete":after_delete.returncode==0 and after_delete.stdout==original}))
except Exception:
 print(json.dumps({"error":"private_reader_probe_failed"}))
 sys.exit(1)
'''


class VerificationError(RuntimeError):
    pass


def invoke(side: str, source: str, arguments: list[str]) -> dict:
    environment = dict(os.environ)
    if side == 'writer':
        for suffix in ('TARGET', 'KEY', 'KNOWN_HOSTS'):
            environment['QNAP_SSH_' + suffix] = environment.get('CLOUD_SSH_' + suffix, '')
        command = shlex.join(['sudo', '-n', '-u', 'usenet', 'python3', '-', *arguments])
    else:
        project = environment.get('QNAP_PROJECT_DIR', '')
        config = environment.get('QNAP_DOCKER_CONFIG_DIR', '')
        if not config:
            if not project.startswith('/share/') or not project.endswith('/compose/qnap'):
                raise VerificationError('scoped_qnap_docker_directory_not_configured')
            config = project.removesuffix('/compose/qnap') + '/state/docker-client'
        command = ('package=$(/sbin/getcfg container-station Install_Path -f /etc/config/qpkg.conf); '
                   'exec "$package/bin/docker" --config ' + shlex.quote(config) + ' ' +
                   shlex.join(['exec', '-i', 'usenet-cache-dashboard-1', 'python3', '-', *arguments]))
    ssh = recon.connection_command(environment)[:-1] + [command]
    process = subprocess.run(ssh, input=source.encode(), stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, timeout=150)
    if process.returncode or len(process.stdout) > 4096:
        raise VerificationError('private_' + side + '_probe_failed')
    result = json.loads(process.stdout)
    if not isinstance(result, dict) or 'error' in result:
        raise VerificationError('private_' + side + '_probe_failed')
    return result


def verify(call=invoke, token: str | None = None) -> dict:
    token = token or uuid.uuid4().hex
    report = {'sentinel_id': token, 'status': 'failed'}
    created_verified = False
    try:
        created = call('writer', WRITER, ['create', token])
        if created.get('created') is not True:
            raise VerificationError('writer_creation_not_verified')
        created_verified = True
        reader = call('reader', READER, [token])
        for field in ('read_matched', 'overwrite_denied', 'delete_denied',
                      'preserved_after_overwrite', 'preserved_after_delete'):
            report[field] = reader.get(field) is True
        for operation in ('overwrite', 'delete'):
            diagnostic = reader.get(operation + '_diagnostic', {})
            allowed = {'exit_code', 'sftp_permission_denied', 'sftp_failure', 'permission_denied',
                       'read_only', 'unsupported', 'connection_failure', 'generic_failure', 'unknown_argument'}
            report[operation + '_diagnostic'] = {key: value for key, value in diagnostic.items()
                                               if key in allowed and type(value) in (int, bool)}
    except Exception:
        report['error'] = 'reader_access_verification_incomplete'
    finally:
        try:
            finished = call('writer', WRITER, ['finish', token, 'created' if created_verified else 'unconfirmed'])
            report['writer_verified_original'] = finished.get('original_preserved') is True
            report['sentinel_cleaned'] = finished.get('cleaned') is True
        except Exception:
            report['sentinel_cleaned'] = False
            report['error'] = 'writer_cleanup_not_confirmed_retry_exact_sentinel'
    required = ('read_matched', 'overwrite_denied', 'delete_denied', 'preserved_after_overwrite',
                'preserved_after_delete', 'writer_verified_original', 'sentinel_cleaned')
    if all(report.get(field) is True for field in required):
        report['status'] = 'passed'
    return report


if __name__ == '__main__':
    report = verify()
    print(json.dumps(report, sort_keys=True))
    raise SystemExit(0 if report['status'] == 'passed' else 1)
