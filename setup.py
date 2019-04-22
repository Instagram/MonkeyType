# Copyright (c) 2017-present, Facebook, Inc.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

import os
from setuptools import setup, find_packages


def long_desc(root_path):
    FILES = ['README.rst', 'CHANGES.rst']
    for filename in FILES:
        filepath = os.path.realpath(os.path.join(root_path, filename))
        if os.path.isfile(filepath):
            with open(filepath, mode='r') as f:
                yield f.read()


HERE = os.path.abspath(os.path.dirname(__file__))
long_description = "\n\n".join(long_desc(HERE))


def get_version(root_path):
    with open(os.path.join(root_path, 'monkeytype', '__init__.py')) as f:
        for line in f:
            if line.startswith('__version__ ='):
                return line.split('=')[1].strip().strip('"\'')


setup(
    name='MonkeyType',
    version=get_version(HERE),
    license="BSD",
    description='Generating type annotations from sampled production types',
    long_description=long_description,
    author='Matt Page',
    author_email='mpage@instagram.com',
    url='https://github.com/instagram/MonkeyType',
    packages=find_packages(exclude=['tests*']),
    package_data={"monkeytype": ["py.typed"]},
    entry_points={
        'console_scripts': [
            'monkeytype=monkeytype.cli:entry_point_main'
        ]
    },
    python_requires='>=3.6',
    install_requires=['retype'],
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
    ],
    zip_safe=False,
)
