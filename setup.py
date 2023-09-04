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
    description='Reads UML Class model from multiple formats (including XMI) and renders them to other formats (including Markdown).',
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
    #install_requires=REQUIREMENTS,
    install_requires=[
        'SQLAlchemy==2.0.20',
        'lxml==4.9.3',
        'lxml-stubs',
        'openpyxl',
        'types-openpyxl',
        'pandas',
        'jinja2'
        ],
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
