#!/usr/bin/python
# -*- coding: utf-8 -*-
from setuptools import find_packages
from setuptools import setup

__version__ = '0.20.0'

setup(
    name='pyramid_zipkin',
    version=__version__,
    provides=["pyramid_zipkin"],
    author='Yelp, Inc.',
    author_email='opensource+pyramid-zipkin@yelp.com',
    license='Copyright Yelp 2017',
    url="https://github.com/Yelp/pyramid_zipkin",
    description='Zipkin instrumentation for the Pyramid framework.',
    packages=find_packages(exclude=('tests*',)),
    package_data={'': ['*.thrift']},
    install_requires=[
        'py_zipkin >= 0.10.1',
        'pyramid',
        'six',
    ],
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "License :: OSI Approved :: Apache Software License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 2.7",
        "Programming Language :: Python :: 3.4",
        "Programming Language :: Python :: 3.5",
        "Programming Language :: Python :: 3.6",
    ],
)
