#!/usr/bin/python
"""
Package setup.
"""

from setuptools import setup, find_packages


def readme():
    """
    Pull the readme contents for the package properties.
    """
    with open('README.md') as readme_file:
        return readme_file.read()


REQUIRES = [
    'msal',
    'pyreadline',
    'requests',
    'ruamel.yaml<=15.66.0',
]

setup(
    name='panoptoindexconnector',
    version='1.0.1',
    author='Stephen Bianamara',
    author_email='sbianamara@panopto.com',
    description=('A general application for connecting a panopto search index to an external source'),
    long_description=readme(),
    keywords=['python', 'panopto', 'connector', 'attivio', 'coveo', 'microsoft_graph'],

    install_requires=REQUIRES,
    package_data={
    },
    # All packages found under src
    package_dir={'': 'src'},
    # Use all packages under src
    packages=find_packages('src'),
    setup_requires=REQUIRES,
    tests_require=[
    ],
    entry_points={
        'console_scripts': [
            'panopto-connector=panoptoindexconnector.connector:main',
        ],
    },
    classifiers=[
        'Development Status :: 4 - Beta',
        'Topic :: Utilities'
    ],
)
