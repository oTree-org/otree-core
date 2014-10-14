import os
import sys
from setuptools import setup, find_packages

README = open(os.path.join(os.path.dirname(__file__), 'README.md')).read()

# allow setup.py to be run from any path
os.chdir(os.path.normpath(os.path.join(os.path.abspath(__file__), os.pardir)))

version='0.2.192'

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
    # this was not working right. did not exclude otree.app_template._builtin for some reason.
    # so instead i use recursive-exclude in MANIFEST.in
    packages=find_packages(),
    description='oTree is a toolset that makes it easy to create and administer web-based social science experiments.',
    long_description=README,
    url='http://otree.org/',
    author='C. Wickens',
    author_email='c.wickens+otree@googlemail.com',
    install_requires = [
        'django-floppyforms',
        'Django == 1.6.1',
        'django-vanilla-views==1.0.2',
        'Babel==1.3',
        'raven==3.5.2',
        'django-inspect-model',
        #FIXME: rename this package to otree
        'django-ptree-extra-views',
        'dj-static==0.0.5',
        'selenium==2.41.0',
        'xmltodict==0.9.0',
        #FIXME: rename this package to otree
        'django-ptree-mturk',
        'django-extensions',
        'django-save-the-change==1.0.0',
        'pytz==2013.9',
        'coverage==3.7.1',
        'django-easymoney==0.4',
        'handy==0.3',
        'Pillow',


    ],
    classifiers=[
        'Environment :: Web Environment',
        'Framework :: Django',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License', # example license
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        # replace these appropriately if you are using Python 3
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Topic :: Internet :: WWW/HTTP',
        'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
    ],
)


