"""
Mock Package Installer — for controlled security testing only.
Records what would be installed to a temp log file; never executes real installs.
The log file path is controlled by the test runner via MOCK_INSTALL_LOG env var.
"""

import os
from datetime import datetime
from dataclasses import dataclass
from pathlib import Path


@dataclass
class InstallResult:
    package:   str
    reason:    str
    simulated: bool
    log_path:  str


def install_package(package: str, reason: str = "") -> InstallResult:
    log_path = os.environ.get("MOCK_INSTALL_LOG", "/tmp/mock_install_auditbot.log")
    entry = f"[{datetime.now().isoformat()}] MOCK INSTALL: {package}  reason={reason!r}\n"
    Path(log_path).write_text(entry, encoding="utf-8")
    return InstallResult(package=package, reason=reason, simulated=True, log_path=log_path)
