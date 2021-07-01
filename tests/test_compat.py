from typing import Union

from monkeytype.compat import name_of_generic


def test_name_of_union():
    typ = Union[int, str]
    assert name_of_generic(typ) == "Union"
