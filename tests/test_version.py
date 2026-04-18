from importlib.metadata import version

import neuralmind


def test_package_version_matches_installed_metadata():
    assert neuralmind.__version__ == version("neuralmind")
