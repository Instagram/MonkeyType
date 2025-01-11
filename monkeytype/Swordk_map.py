# Swordk_map.py
from monkeytype.config import DefaultConfig

class SwordkKeymap(DefaultConfig):
    def get_keymap(self):
        return {
            'q': 's',
            'w': 'w',
            'e': 'o',
            'r': 'r',
            't': 'd',
            'y': 'k',
            'u': 'y',
            'i': 'u',
            'o': 'p',
            'p': 'q',
            '[': '/',
            ']': "'",

            'a': 't',
            's': 'h',
            'd': 'e',
            'f': 'a',
            'g': 'f',
            'h': ',',
            'j': 'l',
            'k': 'g',
            'l': 'i',
            ';': 'n',
            "'": ';',

            'z': 'm',
            'x': 'x',
            'c': 'c',
            'v': 'v',
            'b': 'b',
            'n': 'j',
            'm': '.',
            ',': 'z',
            '.': '[',
            '/': ']'
        }
