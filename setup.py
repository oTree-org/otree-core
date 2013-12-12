import os
import sys
from setuptools import setup, find_packages

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
    version='0.1.79',
    include_package_data=True,
    license='MIT License',
    packages=find_packages(exclude=['ptree.app_template',
                                    'ptree.project_template']),
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
                        'raven==3.5.2',
                        'django-extra-views',

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
    exclude_package_data = {'': ['ptree/app_template/*', 'ptree/project_template/*'],
                            'ptree': ['ptree/app_template/*', 'ptree/project_template/*']}

)

