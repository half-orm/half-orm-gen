#!/usr/bin/env python3
"""
Verify that the half-orm releases half-orm-gen depends on exist on PyPI.

Without --min-*: reads the constraints from pyproject.toml and validates them.
With --min-half-orm / --min-half-orm-dev VERSION: computes >=VERSION,<X.Y+1.0
    (X.Y from half_orm_gen/version.txt), rewrites the constraint in
    pyproject.toml (and in requirements.txt where the package is listed too),
    then validates.

Both packages are checked: half-orm is a hard dependency, half-orm-dev is the
`dev` extra `half_orm gen` needs to discover a project, and an extra pinned
below its published release makes `pip install half-orm-gen[dev]` unsolvable
just as surely as a bad hard dependency.

Exits 1 (and prints an error) if a constraint has no matching release.
"""
import argparse
import json
import re
import sys
import urllib.request
from pathlib import Path

from packaging.specifiers import SpecifierSet
from packaging.version import Version

ROOT = Path(__file__).parent.parent
PYPROJECT = ROOT / 'pyproject.toml'
REQUIREMENTS = ROOT / 'requirements.txt'
VERSION_FILE = ROOT / 'half_orm_gen' / 'version.txt'

PACKAGES = ('half-orm', 'half-orm-dev')


def _constraint_re(package: str) -> re.Pattern:
    """Match `"<package><specifier>"` as spelled in pyproject.toml.

    The trailing character class is what keeps "half-orm" from also matching
    the "half-orm-dev" line: a hyphen is not a specifier operator.
    """
    return re.compile(rf'"{re.escape(package)}(?P<spec>[><=!~][^"]*)"')


def _upper_bound() -> str:
    """The exclusive upper bound derived from half_orm_gen/version.txt.

    half-orm, half-orm-dev and half-orm-gen share their X.Y by convention, so
    a half-orm-gen 1.1.x only ever pairs with a half-orm 1.1.x.
    """
    version_text = VERSION_FILE.read_text(encoding='utf-8').strip()
    match = re.match(r'^(\d+)\.(\d+)\.', version_text)
    if not match:
        print(f'ERROR: cannot parse version "{version_text}"', file=sys.stderr)
        sys.exit(1)
    major, minor = int(match.group(1)), int(match.group(2))
    return f'{major}.{minor + 1}.0'


def _read_constraint(package: str) -> str:
    """The package's current specifier, read from pyproject.toml."""
    match = _constraint_re(package).search(PYPROJECT.read_text(encoding='utf-8'))
    if match is None:
        print(f'ERROR: no {package} constraint found in pyproject.toml', file=sys.stderr)
        sys.exit(1)
    return match.group('spec')


def _current_min(package: str) -> str:
    """The lower bound of the current specifier ('>=1.0.0rc1,<1.1.0' → '1.0.0rc1')."""
    match = re.search(r'>=([^,<\s]+)', _read_constraint(package))
    return match.group(1) if match else ''


def _write_constraint(package: str, constraint: str) -> None:
    """Rewrite the package's specifier in pyproject.toml, and in
    requirements.txt when it lists the package as well — the two drifted
    apart before this script existed (requirements.txt still asked for
    half-orm>=0.16.0 while pyproject.toml had moved to >=1.0.0rc17)."""
    expected = f'"{package}{constraint}"'
    text = PYPROJECT.read_text(encoding='utf-8')
    new_text, count = _constraint_re(package).subn(expected, text)
    if count == 0:
        print(f'ERROR: no {package} constraint found in pyproject.toml', file=sys.stderr)
        sys.exit(1)
    if new_text != text:
        PYPROJECT.write_text(new_text, encoding='utf-8')
        print(f'  pyproject.toml updated: {package}{constraint}')
    else:
        print(f'✓ pyproject.toml already set to {package}{constraint}')

    if not REQUIREMENTS.exists():
        return
    line_re = re.compile(rf'^{re.escape(package)}[><=!~].*$')
    lines = REQUIREMENTS.read_text(encoding='utf-8').splitlines()
    updated = False
    for i, line in enumerate(lines):
        if line_re.match(line) and line != f'{package}{constraint}':
            lines[i] = f'{package}{constraint}'
            updated = True
    if updated:
        REQUIREMENTS.write_text('\n'.join(lines) + '\n', encoding='utf-8')
        print(f'  requirements.txt updated: {package}{constraint}')


def _pypi_versions(package: str) -> list:
    """Every version of *package* PyPI knows about."""
    url = f'https://pypi.org/pypi/{package}/json'
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.load(resp)
    except Exception as exc:
        print(f'ERROR: could not reach PyPI ({exc})', file=sys.stderr)
        sys.exit(1)
    return [Version(v) for v in data['releases']]


def _check(package: str) -> bool:
    """True when a published release satisfies the package's constraint."""
    constraint = _read_constraint(package)
    spec = SpecifierSet(constraint, prereleases=True)
    versions = _pypi_versions(package)
    compatible = sorted((v for v in versions if v in spec), reverse=True)
    if not compatible:
        recent = sorted(versions, reverse=True)[:8]
        print(f'ERROR: no {package} release satisfies {package}{constraint}')
        print(f'  Most recent available: {[str(v) for v in recent]}')
        print()
        print(f'  Release {package} first, then rebuild half-orm-gen.')
        return False
    print(f'✓ {package} {compatible[0]} satisfies {package}{constraint}')
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for package in PACKAGES:
        current = _current_min(package)
        parser.add_argument(
            f'--min-{package}',
            metavar='VERSION',
            default=None,
            help=(
                f'Minimum {package} version. Rewrites the constraint. '
                f'(current: {current or "none"})'
            ),
        )
    args = parser.parse_args()

    for package in PACKAGES:
        minimum = getattr(args, f'min_{package}'.replace('-', '_'))
        if minimum:
            _write_constraint(package, f'>={minimum},<{_upper_bound()}')
        else:
            print(f'✓ pyproject.toml: {package}{_read_constraint(package)}')

    if not all([_check(package) for package in PACKAGES]):
        sys.exit(1)


if __name__ == '__main__':
    main()
