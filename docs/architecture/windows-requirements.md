---
aliases: [Windows Requirements, Windows Native]
tags: [architecture, reference]
type: reference
related: [[HOME]], [[architecture/overview]], [[cli/commands]]
---

← [[HOME]] → [[architecture/overview]]

# Windows Requirements

UPAS is designed to run natively on **Windows 10+** with **PowerShell**. No WSL required.

## Rules Applied Throughout Codebase

| Requirement | Implementation |
|---|---|
| All file paths | `pathlib.Path` — never raw string concatenation |
| Subprocess calls | `subprocess.run(..., shell=False)` with list args |
| Exit codes | `sys.exit(code)` — never `os._exit()` |
| Ctrl+C handling | `signal.signal(signal.SIGINT, handler)` in scheduler |
| No WSL dependency | All tools work via native Python + PowerShell |
| Python version | 3.10+ (for match statements, `|` union types) |
| Virtual env | `.venv\Scripts\Activate.ps1` |

## PowerShell Notes

- Activation: `.venv\Scripts\Activate.ps1`
- If blocked: `Set-ExecutionPolicy RemoteSigned -Scope CurrentUser`
- All CLI commands work in PowerShell, CMD, and Windows Terminal

## Path Handling Example

```python
# ✅ Correct
from pathlib import Path
db_path = Path("data") / "upas.db"

# ❌ Wrong
db_path = "data\\upas.db"  # breaks on Linux, fragile on Windows
```

## Related

[[QUICKSTART]] · [[cli/commands]] · [[architecture/overview]]
