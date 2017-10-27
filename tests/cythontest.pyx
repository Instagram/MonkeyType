from functools import wraps


def cython_deco(fun):
    @wraps(fun)
    def inner(*a, **kw):
        return fun(*a, **kw)

    return inner
