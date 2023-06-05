from setuptools import setup

setup(
    name="amazon-scraper",
    version="1.0.0",
    author="Tejas",
    author_email="tejas75o25@gmail.com",
    description="Some Helpful Classes and Functions for Scraping Amazon Data",
    packages=["src"],
    install_requires=[
        "beautifulsoup4",
        "requests",
    ],
)

try:
    import os

    del os.link
except:
    pass

from setuptools import setup

# import the README
with open("README.rst") as f:
    long_description = f.read()

setup(
    name="amazon_scrape_toolkit",
    version="0.0.1",
    author="Tejas",
    description="Some Helpful Classes and Functions for Scraping Amazon Data",
    long_description=long_description,
    license="MIT",
    url="https://github.com/KidCoderT/amazon-scraper",
    test_suite="tests",
    packages=["src"],
    install_requires=[
        "lxml",
        "beautifulsoup4",
        "requests",
    ],
    platforms=["any"],
    classifiers=(
        "Natural Language :: English",
        "Intended Audience :: Developers",
        "Operating System :: MacOS :: MacOS X",
        "Operating System :: Microsoft :: Windows",
        "Operating System :: POSIX",
        "Programming Language :: Python",
        "License :: OSI Approved :: BSD License",
        "Topic :: Software Development :: Libraries",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Internet",
    ),
)
