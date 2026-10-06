import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills" / "ds2-save" / "scripts"))
sys.path.insert(0, str(ROOT / "skills" / "build-page" / "scripts"))
