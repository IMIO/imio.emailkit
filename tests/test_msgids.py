"""configure.zcml msgids and the msgids.py extraction shim must not drift."""

from pathlib import Path
from xml.etree import ElementTree

import re


PACKAGE = Path(__file__).parent.parent / "src" / "imio" / "emailkit"
EMAILKIT_NS = "{http://namespaces.imio.be/emailkit}"


def zcml_msgids():
    # The parsed file is this repository's own configure.zcml, not input from
    # anywhere, so defusedxml would be a dependency for nothing.
    tree = ElementTree.parse(PACKAGE / "configure.zcml")  # noqa: S314
    msgids = set()
    for element in tree.iter(f"{EMAILKIT_NS}template"):
        for attribute in ("subject", "preheader"):
            value = element.get(attribute)
            if value and value.startswith("["):
                msgids.add(value[1 : value.index("]")])
    return msgids


def shim_msgids():
    source = (PACKAGE / "msgids.py").read_text()
    return set(re.findall(r'_\(\s*"([^"]+)"', source))


def test_every_zcml_msgid_is_extractable():
    assert zcml_msgids() <= shim_msgids()


def test_shim_carries_no_dead_msgids():
    assert shim_msgids() <= zcml_msgids()
