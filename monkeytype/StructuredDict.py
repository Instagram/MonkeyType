from typing import (
    Any,
)


class StructuredDict(dict):

    def __eq__(self, other: Any):
        if not isinstance(other, StructuredDict):
            return False
        return self.__dict__ == other.__dict__

    def __init__(self, **kwargs: Any):
        super().__init__(**kwargs)
        for (key, value) in kwargs.items():
            self.__dict__[key] = value

    def __setitem__(self, key: Any, item: Any):
        self.__dict__[key] = item

    def __getitem__(self, key: Any):
        return self.__dict__[key]

    def __repr__(self):
        return repr(self.__dict__)

    def __len__(self):
        return len(self.__dict__)

    def __delitem__(self, key: Any):
        del self.__dict__[key]

    def clear(self):
        return self.__dict__.clear()

    def copy(self):
        return self.__dict__.copy()

    def has_key(self, key: Any):
        return key in self.__dict__

    def update(self, *args: Any, **kwargs: Any):
        return self.__dict__.update(*args, **kwargs)

    def keys(self):
        return self.__dict__.keys()

    def values(self):
        return self.__dict__.values()

    def items(self):
        return self.__dict__.items()

    def pop(self, *args):
        return self.__dict__.pop(*args)

    def __cmp__(self, dict_: Any):
        return self.__cmp__(self.__dict__, dict_)

    def __contains__(self, item: Any):
        return item in self.__dict__

    def __iter__(self):
        return iter(self.__dict__)


structured_dict_name = 'StructuredDict'
