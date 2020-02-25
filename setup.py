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


setup(
    name='panoptoindexconnector',
    version='1.0.0',
    author='Stephen Bianamara',
    author_email='sbianamara@panopto.com',
    description=('A prototyping of the panopto search index connector'),
    long_description=readme(),
    keywords=['python', 'panopto', 'connector', 'attivio'],

    install_requires=[
        'requests',
        'ruamel.yaml',
    ],
    package_data={
    },
    package_dir={'': 'src'},
    packages=find_packages('src'),
    setup_requires=[
    ],
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
