#!/usr/bin/python
# -*- coding: utf-8 -*-

from setuptools import find_packages
from setuptools import setup

__version__ = "0.11.1"

setup(
    name='pyramid_zipkin',
    version=__version__,
    provides=["pyramid_zipkin"],
    author='Yelp, Inc.',
    author_email='opensource+pyramid-zipkin@yelp.com',
    license='Copyright Yelp 2016',
    url="https://github.com/Yelp/pyramid_zipkin",
    description='Zipkin distributed tracing system support library for pyramid.',
    packages=find_packages(exclude=('tests*', 'testing*', 'tools*')),
    package_data = { '': [ '*.thrift' ] },
    install_requires = [
        'pyramid',
        'six',
        'thriftpy',
    ],
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "License :: OSI Approved :: Apache Software License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 2.6",
        "Programming Language :: Python :: 2.7",
        "Programming Language :: Python :: 3.3",
        "Programming Language :: Python :: 3.4",
    ],
)
