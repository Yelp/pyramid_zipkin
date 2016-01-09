pyramid_zipkin
--------------

Compatible with `py26`, `py27`, `py33`, `py34`.

This project acts as a [Pyramid](http://docs.pylonsproject.org/en/latest/docs/pyramid.html)
tween to facilitate creation of [zipkin](https://github.com/openzipkin/zipkin/wiki) service spans.

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
