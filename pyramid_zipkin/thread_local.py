# -*- coding: utf-8 -*-

import threading

_thread_local = threading.local()

_thread_local.requests = []


def get_zipkin_attrs():
    """Get the topmost level zipkin attributes stored

    :returns: tuple containing zipkin attrs
    :rtype: :class:`zipkin.ZipkinAttrs`
    """
    if _thread_local.requests:
        return _thread_local.requests[-1]


def pop_zipkin_attrs():
    """Pop the topmost level zipkin attributes, if present

    :returns: tuple containing zipkin attrs
    :rtype: :class:`zipkin.ZipkinAttrs`
    """
    if _thread_local.requests:
        return _thread_local.requests.pop()


def push_zipkin_attrs(zipkin_attr):
    """Stores the zipkin attributes to thread local.

    :param zipkin_attr: tuple containing zipkin related attrs
    :type zipkin_attr: :class:`zipkin.ZipkinAttrs`
    """
    _thread_local.requests.append(zipkin_attr)
