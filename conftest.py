"""必须放在项目根：pytest 靠它把根目录加入 sys.path。

让 pytest 始终把项目根加入 sys.path（不依赖 cwd）。"""
import sys
from pathlib import Path

ROOT = Path(__file__).parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))