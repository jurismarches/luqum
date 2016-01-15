# -*- coding: utf-8 -*-
from setuptools import setup

from luqum import __version__


with open('README.rst', 'r') as f:
    long_description = f.read()


setup(
    name='luqum',
    version=__version__,
    description="A Lucene query parser in Python, using PLY",
    long_description=long_description,
    author='Jurismarches',
    author_email='contact@jurismarches.com',
    url='https://github.com/jurismarches/luqum',
    packages=[
        'luqum',
    ],
    install_requires=[
        'ply>=3.8',
    ],
    classifiers=[
        'Development Status :: 3 - Alpha',
        'License :: OSI Approved :: GNU Lesser General Public License v3 or later (LGPLv3+)',
        'Intended Audience :: Developers',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4'
    ],
    test_suite='luqum.tests'
)
