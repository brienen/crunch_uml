import setuptools
import os

long_description = None
with open('README.md', 'r') as fh:
    long_description = fh.read()

setuptools.setup(
    name='crunch_uml',
    version='0.1.3',
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
        'pandas>=1.5,<2',
        'pandas-stubs',
        'jinja2>=3.1.2,<4'
        ],
    extras_require={
        'dev': [
            'black == 23.*',
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
    python_requires='>=3.8, <4',
)
