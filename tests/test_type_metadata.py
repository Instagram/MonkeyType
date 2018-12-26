import pytest

from monkeytype.type_metadata import (
    decode_type_metadata,
    encode_type_metadata,
    get_type_metadata,
    TypeMetadata,
    DictTypeMetadata,
    TypTypeMetadata,
    ListTypeMetadata,
    UnionTypeMetadata,
    AnyTypeMetadata,
    combine_type_metadata,
    decode_type_metadata_from_json,
    TypeMetadataEncodeException,
    TypeMetadataDecodeException,
)


class DummyClass:
    pass


class DummyClass2:
    def __init__(self, val: int):
        self.val = val


class TestTypeMetadata:

    def test_simple_get_type_metadata(self):
        type_metadata1 = get_type_metadata({
            'a': 3,
            'b': {
               'c': [1, 2, '3'],
            },
        })
        assert type_metadata1 == DictTypeMetadata({
            'a': TypTypeMetadata(int),
            'b': DictTypeMetadata({
                'c': ListTypeMetadata(
                    UnionTypeMetadata(
                        set([
                            TypTypeMetadata(int),
                            TypTypeMetadata(str),
                        ]),
                    )
                ),
            }),
        })

    def test_recursion_limited_get_type_metadata(self):
        type_metadata = get_type_metadata({
            'a': {
                'b': {
                    'c': 1,
                },
            },
        }, recursion_max=1)
        assert type_metadata == DictTypeMetadata({
            'a': DictTypeMetadata({
                'b': AnyTypeMetadata(None),
            }),
        })

    def test_encode_decode(self):
        type_metadata = get_type_metadata({
            'a': 3,
            'b': {
                'c': [1, 2, '3', None],
                'd': DummyClass(),
                'e': DummyClass2(1),
            },
        })
        encoded = encode_type_metadata(type_metadata)
        decoded = decode_type_metadata(encoded)
        assert decoded == type_metadata

    def test_invalid_decode(self):
        with pytest.raises(
                TypeMetadataDecodeException
        ):
            decode_type_metadata_from_json('''
                { "kind": "A",
                 "val": "!" }
            ''')

    def test_invalid_encode(self):
        with pytest.raises(
            TypeMetadataEncodeException
        ):
            encode_type_metadata(TypeMetadata(None))

    def test_combine_type_metadata(self):
        num_type_metadata = get_type_metadata(1)
        str_type_metadata = get_type_metadata('string!')
        bool_type_metadata = get_type_metadata(True)

        union_type_metadata = UnionTypeMetadata(set([
            num_type_metadata, str_type_metadata,
        ]))

        assert combine_type_metadata(
            None, num_type_metadata,
        ) == num_type_metadata

        assert combine_type_metadata(
            num_type_metadata, num_type_metadata
        ) == num_type_metadata

        assert combine_type_metadata(
            num_type_metadata, str_type_metadata,
        ) == union_type_metadata

        assert combine_type_metadata(
            union_type_metadata, bool_type_metadata
        ) == UnionTypeMetadata(set([
            num_type_metadata,
            str_type_metadata,
            bool_type_metadata,
        ]))
