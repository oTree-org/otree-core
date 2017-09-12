import os
import sys
from setuptools import setup, find_packages

# allow setup.py to be run from any path
os.chdir(os.path.normpath(os.path.join(os.path.abspath(__file__), os.pardir)))

version = __import__('otree').get_version()

with open('README.rst', encoding='utf-8') as f:
    README = f.read()

with open('requirements.txt', encoding='utf-8') as f:
    required = f.read().splitlines()

with open('requirements_mturk.txt', encoding='utf-8') as f:
    required_mturk = f.read().splitlines()



if sys.argv[-1] == 'publish':

    cmd = "python setup.py sdist upload"
    print(cmd)
    os.system(cmd)

    cmd = 'git tag -a %s -m "version %s"' % (version, version)
    print(cmd)
    os.system(cmd)

    cmd = "git push --tags"
    print(cmd)
    os.system(cmd)

    sys.exit()

if sys.version_info < (3, 5):
    sys.exit('Error: This version of otree-core requires Python 3.5 or higher')

setup(
    name='otree-core',
    version=version,
    include_package_data=True,
    license='MIT License',

    # this was not working right. did not exclude
    # otree.app_template._builtin for some reason. so instead i use
    # recursive-exclude in MANIFEST.in
    packages=find_packages(),
    description=(
        'oTree is a toolset that makes it easy to create and '
        'administer web-based social science experiments.'
    ),
    long_description=README,
    url='http://otree.org/',
    author='chris@otree.org',
    author_email='chris@otree.org',
    install_requires=required,
    classifiers=[
        'Environment :: Web Environment',
        'Framework :: Django',
        'Framework :: Django :: 1.8',
        'Intended Audience :: Developers',
        # example license
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Topic :: Internet :: WWW/HTTP',
        'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
    ],
    entry_points={
        'console_scripts': [
            'otree=otree.management.cli:otree_cli',
        ],
    },
    zip_safe=False,
    extras_require={
        'mturk': required_mturk
    }
)
