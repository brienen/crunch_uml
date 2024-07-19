import setuptools
import os

long_description = None
with open('README.md', 'r') as fh:
    long_description = fh.read()

setuptools.setup(
    name='crunch_uml',
    version='0.2.11',
    description='Reads UML Class model from multiple formats (including XMI) and renders them to other formats (including Markdown).',
    long_description=long_description,
    long_description_content_type="text/markdown",
    url='http://github.com/brienen/crunch_uml',
    author='Arjen Brienen',
    license='MIT',
    include_package_data=True,
    packages=setuptools.find_packages(
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
        'SQLAlchemy>=2.0.20,<3',
        'lxml>=4.9.3,<5',
        'lxml-stubs',
        'openpyxl>=3.0.10,<4',
        'types-openpyxl',
        'numpy==1.26.4',
        'pandas>=2.2.2,<3',
        'pandas-stubs',
        'jinja2>=3.1.2,<4',
        'types-requests>=2.32.0,<3',
        'rdflib>=7.0.0,<8',
        'inflection>=0.5.1,<6',
        'validators>=0.28.0,<1',
        'requests>=2.32.3,<3',
        'jsonschema>=4.22.0,<5',
        'types-jsonschema>=4.22,<5'
        ],
    extras_require={
        'dev': [
            'black == 24.*',
            'build == 0.10.*',
            'flake8 == 6.*',
            'isort == 5.*',
            'mypy == 1.2',
            'pytest == 7.*',
            'pytest-cov == 4.*',
            'twine == 4.*'],
    },
    entry_points={
        'console_scripts': [
            'crunch_uml=crunch_uml.cli:main',
        ]
    },
    python_requires='>=3.9, <4',
)
