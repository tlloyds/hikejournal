from __future__ import annotations

import subprocess
import sys


def test_mobile_api_import_does_not_load_the_web_ui_stack() -> None:
    script = """
import json
import sys
import mobile_api

forbidden = [name for name in ("streamlit", "pandas", "pydeck", "authlib") if name in sys.modules]
print(json.dumps(forbidden))
raise SystemExit(1 if forbidden else 0)
"""

    result = subprocess.run(
        [sys.executable, "-c", script],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    assert result.stdout.strip() == "[]"
