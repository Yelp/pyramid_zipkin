[![Travis](https://img.shields.io/travis/Yelp/pyramid_zipkin.svg)](https://travis-ci.org/Yelp/pyramid_zipkin?branch=master)
[![Coverage Status](https://img.shields.io/coveralls/Yelp/pyramid_zipkin.svg)](https://coveralls.io/r/Yelp/pyramid_zipkin)
[![PyPi version](https://img.shields.io/pypi/v/pyramid_zipkin.svg)](https://pypi.python.org/pypi/pyramid_zipkin/)
[![Supported Python versions](https://img.shields.io/pypi/pyversions/pyramid_zipkin.svg)](https://pypi.python.org/pypi/pyramid_zipkin/)

pyramid_zipkin
--------------

This project provides [Zipkin](https://github.com/openzipkin/zipkin/wiki) instrumentation
for the [Pyramid](http://docs.pylonsproject.org/en/latest/docs/pyramid.html) framework by
using [py_zipkin](https://github.com/Yelp/py_zipkin) under the hood.

Full documentation [here](http://pyramid-zipkin.readthedocs.org/en/latest/).

Features include:

* Blacklisting specific route/paths from getting traced.

* `zipkin_tracing_percent` to control the percentage of requests getting sampled (starting at, and downstream from, this service).

* Creates `http.uri`, `http.uri.qs`, and `status_code` binary annotations automatically for each trace.

Install
-------

```
    pip install pyramid_zipkin
```

Usage
-----

In your service's webapp, you need to include:

```
    config.include('pyramid_zipkin')
```

## Deployment
To bump and deploy a new version after changes have been merged into master, follow these steps:
- `$ git checkout master && git pull`
- update `CHANGELOG.rst` to document the changes
- update `__version__` in `setup.py`
- `$ git add CHANGELOG.rst setup.py && git commit -m 'version <VERSION>'`
- `$ git tag v<VERSION>`
- `$ git push origin master --tags`

License
-------

Copyright (c) 2023, Yelp, Inc. All rights reserved. Apache v2
