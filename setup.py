# Copyright (c) 2017 Presslabs SRL
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


# -*- encoding: utf-8 -*-

import os

import versioneer
from setuptools import setup, find_packages

from silver_braintree import __version__ as version

install_requires = ['braintree']


def read(fname):
    try:
        return open(os.path.join(os.path.dirname(__file__), fname)).read()
    except IOError:
        return ''

setup(
    name="silver-braintree",
    version=version,
    cmdclass=versioneer.get_cmdclass(),
    description=read('DESCRIPTION'),
    long_description=read('README.md'),
    license='Apache 2.0',
    platforms=['OS Independent'],
    keywords='django, app, reusable, billing, invoicing, api',
    author='Presslabs',
    author_email='ping@presslabs.com',
    url='https://github.com/silverapp/silver-braintree',
    packages=find_packages(),
    include_package_data=True,
    install_requires=install_requires,
    classifiers=[
        'Environment :: Web Environment',
        'Framework :: Django :: 1.8',
        'Development Status :: 5 - Production/Stable',
        'License :: OSI Approved :: Apache Software License',
        'Programming Language :: Python :: 2.7'
    ]
)
