import sys
from pathlib import Path

# Ensure the project root is on sys.path so both 'src' and 'Ammeters' are importable
sys.path.insert(0, str(Path(__file__).parent))
