#!c:\users\frederik\code\ku\otree-core\venv\scripts\python.exe
# EASY-INSTALL-ENTRY-SCRIPT: 'otree','console_scripts','otree'
__requires__ = 'otree'
import re
import sys
from pkg_resources import load_entry_point

if __name__ == '__main__':
    sys.argv[0] = re.sub(r'(-script\.pyw?|\.exe)?$', '', sys.argv[0])
    sys.exit(
        load_entry_point('otree', 'console_scripts', 'otree')()
    )
