"""Shim so that the package can be a zc.buildout develop egg.

Same reason as ``imio.emailkit``'s own ``setup.py``, and here it is not merely a
convenience: ``zc.buildout``'s ``develop`` runs ``setup.py`` directly, and this
distribution *is* a buildout recipe. Without this file a checkout could not be
develop-installed by the very tool it extends.

The metadata lives in ``pyproject.toml`` in PEP 621 form and setuptools reads it
from there; the two arguments below are restated only because
``check-python-versions`` reads ``setup.py`` statically.
"""

from setuptools import setup


setup(
    python_requires=">=3.10,<3.14",
    classifiers=[
        "Programming Language :: Python",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
    ],
)
