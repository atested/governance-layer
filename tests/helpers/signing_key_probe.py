#!/usr/bin/env python3
import importlib.util
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
POLICY_EVAL_PATH = Path(os.environ.get("POLICY_EVAL_PATH", REPO_ROOT / "scripts" / "policy-eval.py"))

try:
    spec = importlib.util.spec_from_file_location("policy_eval", POLICY_EVAL_PATH)
    policy_eval = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(policy_eval)
except Exception as exc:
    msg = f"FATAL: failed to load policy-eval: {exc}"
    print("MODE=LOAD_ERROR")
    print("RC=1")
    print(f"FATAL={msg}")
    sys.exit(1)

HOME = Path(os.environ.get("HOME", Path.home()))
GOV_SIGNING_KEY_PATH = os.environ.get("GOV_SIGNING_KEY_PATH")
default_key = HOME / ".config" / "gov-layer" / "signing.key"
if GOV_SIGNING_KEY_PATH:
    mode = "GOV_KEY"
elif default_key.exists():
    mode = "DEFAULT_KEY"
else:
    mode = "NO_KEY"

fatal = None
has_key = False
rc = 0
try:
    priv, key_id, err = policy_eval.load_signing_private_key()
    has_key = priv is not None
    if err is not None:
        fatal = err
        rc = 1
except Exception as exc:
    fatal = f"FATAL: unexpected exception: {exc}"
    rc = 1

print(f"MODE={mode}")
print(f"RC={rc}")
print(f"FATAL={fatal or ''}")
sys.exit(rc)
