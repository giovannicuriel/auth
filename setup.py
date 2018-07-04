# -*- coding: utf-8 -*-
import os

import setuptools

from pip._internal import download
from pip._internal import req


HERE = os.path.abspath(os.path.dirname(__file__))


def get_requirements(reqfile):
    path = os.path.join(HERE, reqfile)
    deps = req.parse_requirements(path, session=download.PipSession())
    return [str(ir.req) for ir in deps]

setuptools.setup(
    name='auth',
    description='Dojot authentication service',
    version=':versiontools:auth:',
    packages=setuptools.find_packages(),
    package_data={"auth": ["templates/*"]},
    include_package_data=True,
    install_requires=get_requirements('requirements/requirements.txt'),
    setup_requires='versiontools',

    author='Matheus Magalhaes',
    author_email='matheusr@cpqd.com.br',
    url='dojot.com.br',
)
