import tomllib
from pathlib import Path

import hydra

ROOT = Path(__file__).resolve().parents[1]


def test_package_version_matches_project_metadata() -> None:
    data = tomllib.loads((ROOT / "pyproject.toml").read_text())

    assert hydra.__version__ == data["project"]["version"]


def test_pyproject_packages_fathom_sources_and_license() -> None:
    data = tomllib.loads((ROOT / "pyproject.toml").read_text())

    assert "hydra/native/fathom/LICENSE" in data["project"]["license-files"]
    package_data = data["tool"]["setuptools"]["package-data"]["hydra"]

    assert "native/fathom/LICENSE" in package_data
    assert "native/fathom/*.c" in package_data
    assert "native/fathom/*.cpp" in package_data
    assert "native/fathom/*.h" in package_data


def test_release_workflow_uses_the_single_build_entry_point() -> None:
    """The release build must go through tools/build_release.py on Python 3.12."""
    workflow = (ROOT / ".github" / "workflows" / "build.yml").read_text()

    assert 'python-version: "3.12"' in workflow
    assert "python tools/build_release.py" in workflow
    assert "native Syzygy extension check" in workflow


def test_build_release_is_mypyc_compiled_and_bundles_fathom_before_pyinstaller() -> None:
    """The released executables must be the mypyc-compiled build (not pure Python),
    with the native Fathom/Syzygy extension built before PyInstaller bundles it."""
    build_release = ROOT / "tools" / "build_release.py"
    assert build_release.is_file()
    script = build_release.read_text()

    # Order the actual command invocations (quoted args are code-only, so their
    # first occurrence is not confused by the docstring prose).
    build_ext = script.index('"build_ext"')
    mypyc = script.index('"mypyc"')
    pyinstaller = script.index('"PyInstaller"')

    assert build_ext < mypyc < pyinstaller
    assert '"--add-binary"' in script  # bundle the mypyc runtime
