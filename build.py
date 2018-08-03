import subprocess
import os

os.chdir('docs')
subprocess.check_call(['make', 'html'])

os.chdir('..')

doc_text = open('bitpit.py').read().split("'''", 2)[1]
tutorial_text = '''
--------
Tutorial
--------

Check out bitpit tutorial at http://bitpit.readthedocs.io/
'''

readme_text = doc_text.lstrip() + tutorial_text

with open('README.txt', 'w') as f:
    print(readme_text, file=f)

subprocess.check_call(['python3', 'setup.py', 'sdist'])
