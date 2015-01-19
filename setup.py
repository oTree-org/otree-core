import os
import sys

from setuptools import setup, find_packages


README = open(os.path.join(os.path.dirname(__file__), 'README.md')).read()


REQUIREMENTS = [
    'Babel>=1.3',
    'Django>=1.7.1',
    'coverage>=3.7.1',
    'dj-static>=0.0.6',
    'django-celery>=3.1.16',
    'django-countries>=3.0.1',
    'django-easymoney>=0.5',
    'django-extensions>=1.4.6',
    'django-ptree-extra-views>=0.6.3',
    'django-floppyforms>=1.2.0',
    'django-inspect-model>=0.7',
    'django-ptree-mturk>=1.0.1',
    'django-save-the-change>=1.0.0',
    'django-vanilla-views>=1.0.2',
    'flake8>=2.2.5',
    'handy>=0.3',
    'mock>=1.0.0',
    'pytz>=2013.9',
    'raven>=5.1.1',
    'selenium>=2.41.0',
    'xmltodict>=0.9.0'
]

# allow setup.py to be run from any path
os.chdir(os.path.normpath(os.path.join(os.path.abspath(__file__), os.pardir)))

version = '0.2.257'


if sys.argv[-1] == 'publish':

    cmd = "python setup.py sdist upload"
    print(cmd)
    os.system(cmd)

    cmd = 'git tag -a %s -m "version %s"' % (version, version)
    print cmd
    os.system(cmd)

    cmd = "git push --tags"
    print cmd
    os.system(cmd)

    sys.exit()


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
    author='C. Wickens',
    author_email='c.wickens+otree@googlemail.com',
    install_requires = REQUIREMENTS,
    classifiers=[
        'Environment :: Web Environment',
        'Framework :: Django',
        'Intended Audience :: Developers',
        # example license
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        # replace these appropriately if you are using Python 3
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Topic :: Internet :: WWW/HTTP',
        'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
    ],
)
