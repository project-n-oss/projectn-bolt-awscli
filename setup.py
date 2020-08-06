#!/usr/bin/env python
from setuptools import setup

requires = ['awscli>=1.12.13', 'botocore>=1.12.13']
python_requires = '>=3'

setup(
    name='awscli-plugin-bolt',
    packages=['awscli-plugin-bolt'],
    version='0.1.0',
    description='Bolt plugin for AWS CLI',
    long_description=open('README.md').read(),
    author='Project N',
    install_requires=requires,
    classifiers=[],
    python_requires=python_requires
)
