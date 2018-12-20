from monkeytype.type_metadata import (
    decode_type_metadata,
    encode_type_metadata,
    get_type_metadata, DictTypeMetadata, TypTypeMetadata, ListTypeMetadata, UnionTypeMetadata)


class TestTypeMetadata:

    def test_get_type_metadata(self):
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

    def test_encode_decode_type_metadata(self):
        type_metadata = get_type_metadata({
            'a': 3,
            'b': {
                'c': [1, 2, '3'],
            },
        })
        encoded = encode_type_metadata(type_metadata)
        decoded = decode_type_metadata(encoded)
        assert decoded == type_metadata
