"""Resource locations shared by source builds and the standalone executable."""
from pathlib import Path
import sys
ROOT=Path(sys._MEIPASS) if getattr(sys,'frozen',False) else Path(__file__).resolve().parents[1]
SOURCE_ROOT=ROOT/'src'
