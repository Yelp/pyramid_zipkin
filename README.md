[![Travis](https://img.shields.io/travis/Yelp/pyramid_zipkin.svg)](https://travis-ci.org/Yelp/pyramid_zipkin?branch=master)
[![Coverage Status](https://img.shields.io/coveralls/Yelp/pyramid_zipkin.svg)](https://coveralls.io/r/Yelp/pyramid_zipkin)
[![PyPi version](https://img.shields.io/pypi/v/pyramid_zipkin.svg)](https://pypi.python.org/pypi/pyramid_zipkin/)
[![Supported Python versions](https://img.shields.io/pypi/pyversions/pyramid_zipkin.svg)](https://pypi.python.org/pypi/pyramid_zipkin/)

pyramid_zipkin
--------------

This project acts as a [Pyramid](http://docs.pylonsproject.org/en/latest/docs/pyramid.html)
tween to facilitate creation of [zipkin](https://github.com/openzipkin/zipkin/wiki) service spans.

Full documentation [here](http://pyramid-zipkin.readthedocs.org/en/latest/).

Features include:

* Blacklisting specific route/paths from getting traced.

* `zipkin_tracing_percent` to control the %age of requests getting sampled.

* API `create_headers_for_new_span` to generate new client headers.

* Creates `http.uri` binary annotation automatically for each trace.

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

License
-------

Copyright (c) 2016, Yelp, Inc. All rights reserved. Apache v2
