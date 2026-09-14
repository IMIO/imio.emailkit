Prepare the first PyPI release of both distributions in this repository.
`imio.emailkit` and `imio.recipe.emailkit` each get a `Development Status :: 4 -
Beta` classifier, a `setuptools>=77` build requirement (the declared 68.2 floor
could never have built the PEP 639 SPDX `license` field; it only worked because
PEP 517 isolation fetches a newer setuptools), and a prefixed zest.releaser
`tag-format`, because one git repository shipping two distributions has one tag
namespace and a colliding bare version tag makes zest.releaser build the wrong
one. The recipe also gains its own `LICENSE.GPL`, having declared `GPL-2.0-only`
while shipping no licence text.
