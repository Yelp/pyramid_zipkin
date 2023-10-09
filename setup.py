#!/usr/bin/python
from setuptools import find_packages
from setuptools import setup

__version__ = '2.2.0'

setup(
    name='pyramid_zipkin',
    version=__version__,
    provides=["pyramid_zipkin"],
    author='Yelp, Inc.',
    author_email='opensource+pyramid-zipkin@yelp.com',
    license='Copyright Yelp 2018',
    url="https://github.com/Yelp/pyramid_zipkin",
    description='Zipkin instrumentation for the Pyramid framework.',
    packages=find_packages(exclude=('tests*',)),
    package_data={
        '': ['*.thrift'],
        'pyramid_zipkin': ['py.typed'],
    },
    install_requires=[
        'py_zipkin >= 0.18.1',
        'pyramid',
    ],
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "License :: OSI Approved :: Apache Software License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
    ],
    python_requires=">=3.7",
)
