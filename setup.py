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
    requires=['argparse'],
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'Intended Audience :: Information Technology',
        'License :: OSI Approved :: Apache Software License',
        'Natural Language :: English',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7',
        'Topic :: Utilities',
        ],
    )
