"""Ruleset loader for OSRIC data and configuration.

Supports overriding files via the OSRIC_RULESET_DIR environment variable.
A mod directory should mirror the structure of rulesets/osric/:

    data/       # classes.yaml, equipment.yaml, etc.
    config/     # core.yaml, rolling.yaml, progression.yaml, combat.yaml
    spells/     # spells.yaml, class_spells.yaml
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml


_DEFAULT_DIR = Path(__file__).parent


def _ruleset_dir() -> Path:
    override = os.environ.get("OSRIC_RULESET_DIR")
    if override:
        return Path(override)
    return _DEFAULT_DIR


def _load_yaml(path: Path) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_data(name: str) -> Any:
    """Load a YAML file from the data directory."""
    path = _ruleset_dir() / "data" / name
    if not path.exists():
        path = _DEFAULT_DIR / "data" / name
    return _load_yaml(path)


def load_config(name: str) -> Any:
    """Load a YAML file from the config directory."""
    path = _ruleset_dir() / "config" / name
    if not path.exists():
        path = _DEFAULT_DIR / "config" / name
    return _load_yaml(path)


def load_spells(name: str) -> Any:
    """Load a YAML file from the spells directory."""
    path = _ruleset_dir() / "spells" / name
    if not path.exists():
        path = _DEFAULT_DIR / "spells" / name
    return _load_yaml(path)
