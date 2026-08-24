"""Compatibility shim — canonical module is tenshin_auth.

Games import tenshin_gate; hub imports session. Both re-export tenshin_auth.
See website/SSOT.md and website/dropins/tenshin_auth.py.
"""
from tenshin_auth import *  # noqa: F403
