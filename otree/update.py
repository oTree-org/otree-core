import re
from pathlib import Path
from typing import Optional

from otree import __version__


def split_dotted_version(version):
    return tuple([int(n) for n in version.split('.')])


def check_update_needed(
    requirements_path: Path, current_version=__version__
) -> Optional[str]:
    '''rewrote this without pkg_resources since that takes 0.4 seconds just to import'''

    if not requirements_path.exists():
        return

    try:
        current_version_tuple = split_dotted_version(current_version)
    except ValueError:
        return

    for line in requirements_path.read_text('utf8').splitlines():
        res = check_update_needed_line(line.strip(), current_version_tuple)
        if res:
            return f'''This project requires a different oTree version. Enter: pip3 install "{line}"'''


def check_update_needed_line(line, current_version: tuple):
    # simpler if we don't have to deal with any extra content on the line,
    # such as a comment that might contain a version number etc.

    def check(rhs_fmt):
        lhs = 'otree(\[mturk\])?'
        rhs = rhs_fmt.format(VERSION='([\d\.]+)')
        match = re.match(lhs + rhs, line)
        if match:
            groups = match.groups()[1:]
            try:
                return [split_dotted_version(g) for g in groups]
            except ValueError:
                pass

    match = check('=={VERSION}')
    if match:
        [version] = match
        if current_version != version:
            return True

    match = check('>={VERSION}')
    if match:
        [version] = match
        if current_version < version:
            return True

    match = check('>={VERSION},<{VERSION}')
    if match:
        [version, too_high_version] = match
        if current_version < version or current_version >= too_high_version:
            return True

    return False
