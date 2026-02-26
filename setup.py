from setuptools import setup, find_packages

setup(
    name='rws-common',
    version='0.1',
    packages=find_packages(),
    platforms='any',
    install_requires=[
        'Flask',
        'honeycomb-beeline==2.12.1'
    ]
)
