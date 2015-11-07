#!/usr/bin/python
# -*- coding: utf-8 -*-

from setuptools import find_packages
from setuptools import setup

__version__ = "0.1.0"

setup(
    name='pyramid_zipkin',
    version=__version__,
    provides=["pyramid_zipkin"],
    author='Yelp, Inc.',
    author_email='opensource+pyramid-zipkin@yelp.com',
    license='Copyright Yelp 2015',
    url="https://github.com/Yelp/pyramid_zipkin",
    description='Zipkin distributed tracing system support library for pyramid.',
    packages=find_packages(exclude=('tests*', 'testing*', 'tools*')),
    install_requires = [
        'pyramid',
        'Thrift',
    ],
)
