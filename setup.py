import os
import sys
from setuptools import setup, find_packages
import shutil
from pathlib import Path

# allow setup.py to be run from any path
os.chdir(os.path.normpath(os.path.join(os.path.abspath(__file__), os.pardir)))

import otree

version = otree.__version__

SUPPORTED_PY3_VERSIONS = [7, 8, 9, 10, 11, 12, 13]

# make it visible so it stands out from the rest of the spew
MSG_PY_VERSION = """
**********************************************************************************
* Error: This version of oTree is only compatible with these Python versions:
* {}
**********************************************************************************
""".format(
    ', '.join(f'3.{x}' for x in SUPPORTED_PY3_VERSIONS)
)


if sys.version_info[0] != 3 or sys.version_info[1] not in SUPPORTED_PY3_VERSIONS:
    sys.exit(MSG_PY_VERSION)


def clean_requirements(requirements_text):
    required_raw = requirements_text.splitlines()
    required = []
    for line in required_raw:
        req = line.split('#')[0].strip()
        if req:
            required.append(req)
    return required


README = Path('README.rst').read_text('utf8')
required = clean_requirements(Path('requirements.txt').read_text())


if sys.argv[-1] == 'publish':

    if Path('dist').is_dir():
        shutil.rmtree('dist')
    for cmd in [
        "python setup.py sdist",
        "twine upload dist/*",
        f'git tag -a {version} -m "version {version}"',
        "git push --tags",
    ]:
        sys.stdout.write(cmd + '\n')
        exit_code = os.system(cmd)
        if exit_code != 0:
            raise AssertionError
    if Path('build').is_dir():
        shutil.rmtree('build')

    sys.exit()


setup(
    name='otree',
    version=version,
    include_package_data=True,
    license='MIT License',
    # 2017-10-03: find_packages function works correctly, but tests
    # are still being included in the package.
    # not sure why. so instead i use
    # recursive-exclude in MANIFEST.in.
    packages=find_packages(),
    description=('Framework for multiplayer strategy games and complex surveys.'),
    long_description=README,
    url='http://otree.org/',
    author='chris@otree.org',
    author_email='chris@otree.org',
    install_requires=required,
    entry_points={'console_scripts': ['otree=otree.main:execute_from_command_line']},
    zip_safe=False,
    # we no longer need boto but people might still have [mturk] in their reqs files
    extras_require={'mturk': []},
)
