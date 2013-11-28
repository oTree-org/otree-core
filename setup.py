import os
import sys
from setuptools import setup

README = open(os.path.join(os.path.dirname(__file__), 'README.rst')).read()

# allow setup.py to be run from any path
os.chdir(os.path.normpath(os.path.join(os.path.abspath(__file__), os.pardir)))

if sys.argv[-1] == 'publish':
    os.system("python setup.py sdist upload")
    print("You probably want to also tag the version now:")
    print("  git tag -a %s -m 'version %s'" % (version, version))
    print("  git push --tags")
    sys.exit()

setup(
    name='django-ptree',
    version='0.1.48',
    packages=['ptree',
              'ptree.models',
              'ptree.management',
              'ptree.sequence_of_experiments',
              'ptree.templatetags',
              'ptree.views',
              'ptree.questionnaires',
              'ptree.questionnaires.life_orientation_test',
              'ptree.management.commands'],
    include_package_data=True,
    license='MIT License',
    description='pTree is a Django toolset that makes it easy to create and administer social science experiments to online participants.',
    long_description=README,
    url='http://ptree.org/',
    author='Chris Wickens',
    author_email='c.wickens+ptree@googlemail.com',
    install_requires = ['boto==2.13.3',
                        'django-crispy-forms==1.4.0',
                        'Django == 1.6.0',
                        'django-data-exports==0.6',
                        'django-vanilla-views==1.0.2',
                        'Babel==1.3',

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