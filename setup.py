import os
import sys

from setuptools import setup, find_packages


README = open(os.path.join(os.path.dirname(__file__), 'README.md')).read()


REQUIREMENTS = [
    'Babel>=1.3',
    'boto>=2.38',
    'Django>=1.8',
    'coverage>=3.7',
    'dj-database-url>=0.2',
    'django-celery>=3.1',
    'django-cors-headers>=1.1',
    'django-countries>=3.3',
    'django-easymoney>=0.5',
    'django-extensions>=1.5',
    'django-floppyforms>=1.5.1',
    'django-idmap>=0.3.3',
    'django-inspect-model>=0.7',
    'django-sslify>=0.2.7',
    'django-sslserver>=0.15',
    'django-vanilla-views>=1.0',
    'djangorestframework>=3.1',
    'handy>=0.5.2',
    'honcho>=0.6.6',
    'IPy>=0.83',
    'mock>=1.0',
    'ordered-set>=1.3',
    'otree-save-the-change>=1.1.3',
    'pytz>=2015.4',
    'raven>=5.4',
    'requests>=2.7',
    'selenium>=2.46',
    'whitenoise>=2.0.2',
    'xmltodict>=0.9',

    # Remove this when save-the-change > 1.1.0 is out
    'otree-save-the-change'
]


# allow setup.py to be run from any path
os.chdir(os.path.normpath(os.path.join(os.path.abspath(__file__), os.pardir)))

# please change the version on otree/__init__.py
version = __import__('otree').get_version()


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
    install_requires=REQUIREMENTS,
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
    entry_points = {
        'console_scripts': [
            'otree=otree.management.cli:otree_cli',
            'otree-heroku=otree.management.cli:otree_heroku_cli',
        ],
    }
)
