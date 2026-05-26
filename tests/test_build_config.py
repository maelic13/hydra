import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_pyproject_packages_fathom_sources_and_license() -> None:
    data = tomllib.loads((ROOT / "pyproject.toml").read_text())

    assert "hydra/native/fathom/LICENSE" in data["project"]["license-files"]
    package_data = data["tool"]["setuptools"]["package-data"]["hydra"]

    assert "native/fathom/LICENSE" in package_data
    assert "native/fathom/*.c" in package_data
    assert "native/fathom/*.cpp" in package_data
    assert "native/fathom/*.h" in package_data


def test_release_workflow_builds_native_extension_before_pyinstaller() -> None:
    workflow = (ROOT / ".github" / "workflows" / "build.yml").read_text()

    build_ext = workflow.index("python setup.py build_ext --inplace")
    pyinstaller = workflow.index("pyinstaller --clean --onefile")

    assert 'python-version: "3.12"' in workflow
    assert build_ext < pyinstaller
    assert "native Syzygy extension check" in workflow
