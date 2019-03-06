from setuptools import setup

setup(
    name='eculib',
    version='1.0.9',
    description='A library for K-line based ECU communication',
    url='https://github.com/MCU-Innovations/eculib',
    author='Ryan M. Hope',
    author_email='ryan.hope@mcuinnovations.com',
    license='GPL-3',
    packages=['eculib'],
    entry_points={
        'console_scripts': ['eculib=eculib.__main__:Main'],
    },
    install_requires=['pylibftdi','pydispatcher'],
)
