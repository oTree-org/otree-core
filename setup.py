import os
import sys
from setuptools import setup, find_packages
import shutil

README = open(os.path.join(os.path.dirname(__file__), 'README.md')).read()

# allow setup.py to be run from any path
os.chdir(os.path.normpath(os.path.join(os.path.abspath(__file__), os.pardir)))

version='0.2.151'

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

otree_script = 'bin/otree'
with open(otree_script, 'r') as f:
    t = f.read()
with open(otree_script, 'w') as f:
    f.write(t.replace('\r', ''))


# FIXME: what if the user cloned from github and ran 'python setup.py install'?
if 'sdist' in sys.argv:
    shutil.make_archive('otree/app_template', 'zip', 'otree/app_template')
    shutil.make_archive('otree/project_template', 'zip', 'otree/project_template')

setup(
    name='django-otree',
    version=version,
    include_package_data=True,
    license='MIT License',
    # this was not working right. did not exclude otree.app_template.utilities for some reason.
    # so instead i use recursive-exclude in MANIFEST.in
    packages=find_packages(),
    description='oTree is a Django toolset that makes it easy to create and administer web-based social science experiments.',
    long_description=README,
    url='http://otree.org/',
    author='Chris Wickens',
    author_email='c.wickens+otree@googlemail.com',
    install_requires = [
        'django-crispy-forms==1.4.0',
        'Django == 1.6.1',
        'django-vanilla-views==1.0.2',
        'Babel==1.3',
        'raven==3.5.2',
        'django-inspect-model',
        'django-otree-extra-views',
        'dj-static==0.0.5',
        'selenium==2.41.0',
        'xmltodict==0.9.0',
        'django-otree-mturk',
        'django-extensions',
        'django-save-the-change==1.0.0',
        'pytz==2013.9',
        'coverage==3.7.1',
        'django-easymoney==0.3.5',
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
    scripts = ['bin/otree'],

)


