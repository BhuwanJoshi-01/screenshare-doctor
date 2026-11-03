from importlib.metadata import version

import screenshare_doctor


def test_version_comes_from_installed_metadata() -> None:
    assert screenshare_doctor.__version__ == version("screenshare-doctor")
