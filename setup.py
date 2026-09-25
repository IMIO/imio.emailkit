"""Shim so the package can be a zc.buildout develop egg.

Metadata lives in ``pyproject.toml``; the arguments below are restated only
because ``check-python-versions`` reads ``setup.py`` statically.
"""

from setuptools import setup


setup(
    python_requires=">=3.12,<3.15",
    classifiers=[
        "Programming Language :: Python",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
        "Programming Language :: Python :: 3.14",
    ],
)
