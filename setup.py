import setuptools
import os

long_description = None
with open('README.md', 'r') as fh:
    long_description = fh.read()

with open('requirements.txt') as f:
    required = f.read().splitlines()
required = [item for item in required if not item.startswith('#')]
REQUIREMENTS = required

required = None
with open('dev_requirements.txt') as f:
    required = f.read().splitlines()
required = [item for item in required if not item.startswith('#')]
DEV_REQUIREMENTS = required

setuptools.setup(
    name='crunch_uml',
    version='0.1.0',
    description='XMI-Parser that renders to multiple formats.',
    long_description=long_description,
    long_description_content_type="text/markdown",
    url='http://github.com/brienen/crunch_uml',
    author='Arjen Brienen',
    license='MIT',
    packages=setuptools.get_packages(
        exclude=[
            'examples',
            'test',
        ]
    ),
    package_data={
        'crunch_uml': [
            'py.typed',
        ]
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    install_requires=REQUIREMENTS,
    extras_require={
        'dev': DEV_REQUIREMENTS,
    },
    entry_points={
        'console_scripts': [
            'crunch_uml=crunch_uml.cli:main',
        ]
    },
    python_requires='>=3.8, <4',
)
