import setuptools
import os
import crunch_uml.const as const

long_description = None
with open('README.md', 'r') as fh:
    long_description = fh.read()

# Lees het requirements.txt bestand en gebruik het voor install_requires
def parse_requirements(filename):
    with open(filename, 'r') as f:
        return f.read().splitlines()

setuptools.setup(
    name='crunch_uml',
    version='0.2.12',
    description="Crunch_uml reads UML Class model from multiple formats (including XMI, Enterprise Architect XMI, Excel, Json, and others), can perform transformations and renders them to other formats (including Markdown, json, json schema and many others).",
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
    install_requires=parse_requirements('requirements.txt'),
    extras_require={
        'dev':[
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
