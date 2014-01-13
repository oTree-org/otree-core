#/usr/bin/env python
# running this script will generate a file called 'field_descriptions.txt'
# that can be sent to the person analyzing the data


import os
import shutil
os.system('sphinx-build -b text . .')

try:
    shutil.rmtree('.doctrees')
except:
    pass