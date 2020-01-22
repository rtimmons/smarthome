from setuptools import setup

setup(
    name="hassmetaconfig",
    version="0.0.1",
    description="Generate Home-Assistant.io configs from simpler yamls",
    long_description="",
    author="Ryan Timmons",
    author_email="ryan <at> rytim.com",
    maintainer="Ryan Timmons",
    maintainer_email="ryan <at> rytim.com",
    url="http://github.com/rtimmons/smarthome",
    keywords=[],
    install_requires=[],
    license="Apache License, Version 2.0",
    python_requires=">=3.5",
    classifiers=[],
    packages=['hassmetaconfig'],
    zip_safe=True,
    entry_points={
        'console_scripts': [
            'hassmetagen = hassmetaconfig.cli:main'
        ]
    }
)
