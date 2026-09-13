#!/usr/bin/env python3
"""Generate a PBKDF2 password hash for an operator login.

    python3 scripts/make_password_hash.py 'the-password'

Paste the printed value into the CAEL_PASSWORD_HASH / SHEYLYN_PASSWORD_HASH env var
(server-side only). The plaintext password is never stored anywhere.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app"))
import auth

if len(sys.argv) != 2:
    sys.exit("usage: python3 scripts/make_password_hash.py '<password>'")
print(auth.hash_password(sys.argv[1]))
