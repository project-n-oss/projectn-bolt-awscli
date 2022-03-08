#!/usr/bin/env python
from setuptools import setup

requires = ['awscli>=1.12.13', 'botocore>=1.12.13']
python_requires = '>=3'

setup(
    name='awscli-plugin-bolt',
    packages=['awscli-plugin-bolt'],
    version='2.0.1',
    description='Bolt plugin for AWS CLI',
    long_description=open('README.md').read(),
    long_description_content_type='text/markdown',
    author='Project N',
    install_requires=requires,
    python_requires=python_requires,
    classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: OS Independent",
        "License :: OSI Approved :: Apache Software License",
    ],
    url="https://gitlab.com/projectn-oss/projectn-bolt-awscli",
)
