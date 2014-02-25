import os
import sys
from setuptools import setup, find_packages
import shutil

README = open(os.path.join(os.path.dirname(__file__), 'README.rst')).read()

# allow setup.py to be run from any path
os.chdir(os.path.normpath(os.path.join(os.path.abspath(__file__), os.pardir)))

version='0.2.65'

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

ptree_script = 'bin/ptree'
with open(ptree_script, 'r') as f:
    t = f.read()
with open(ptree_script, 'w') as f:
    f.write(t.replace('\r', ''))


# FIXME: what if the user cloned from github and ran 'python setup.py install'?
if 'sdist' in sys.argv:
    shutil.make_archive('ptree/app_template', 'zip', 'ptree/app_template')
    shutil.make_archive('ptree/project_template', 'zip', 'ptree/project_template')

setup(
    name='django-ptree',
    version=version,
    include_package_data=True,
    license='MIT License',
    packages=find_packages(exclude=['ptree.app_template',
                                    'ptree.project_template']),
    description='pTree is a Django toolset that makes it easy to create and administer social science subsessions to online participants.',
    long_description=README,
    url='http://ptree.org/',
    author='Chris Wickens',
    author_email='c.wickens+ptree@googlemail.com',
    install_requires = [
        'boto==2.13.3',
        'django-crispy-forms==1.4.0',
        'Django == 1.6.1',
        'django-vanilla-views==1.0.2',
        'Babel==1.3',
        'raven==3.5.2',
        'django-extra-views',
        'django-inspect-model',
    ],
    dependency_links = [
        'http://github.com/tomchristie/django-extra-views/tarball/master#egg=django-extra-views',
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
    scripts = ['bin/ptree'],

)

