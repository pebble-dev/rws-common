from setuptools import setup

setup(
    name='rws-common',
    version='0.1',
    packages=setuptools.find_packages(),
    platforms='any',
    install_requires=[
        'Flask',
        'honeycomb-beeline==2.12.1'
    ]
)
