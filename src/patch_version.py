"""One version shared by source builds and the frozen installer."""
import re
from paths import ROOT

VERSION = (ROOT / 'VERSION').read_text(encoding='ascii').strip()
if not re.fullmatch(r'(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)', VERSION):
    raise ValueError('VERSION must be MAJOR.MINOR.PATCH')
