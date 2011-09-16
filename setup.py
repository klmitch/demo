#!/usr/bin/python

from distutils.core import setup

setup(
    name='Demo',
    version='0.1',
    description="Demo Script Driver",
    author="Kevin L. Mitchell",
    author_email="kevin.mitchell@rackspace.com",
    url="http://github.com/klmitch/demo",
    scripts=['bin/demo'],
    packages=['demo'],
    license="LICENSE.txt",
    long_description=open('README.rst').read(),
    classifiers=[
        'Development Status :: 3 - Alpha',
        ],
    )
