import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from deprecated_parameters import generate_stub
from deprecated_parameters._stubgen import main

pytest.importorskip("mypy", reason="mypy not installed")

from deprecated_parameters_tests.test_mypy import make_mypy_ini  # noqa: E402

module_source = """
from deprecated_parameters import (
    deprecated_parameters,
    ParameterRemove,
    ParameterRename,
    ParameterPositional,
    ParameterValueRemove,
)

@deprecated_parameters(ParameterRemove(old_name="verbose", when="v2.0.0"))
def removed(data: list) -> list:
    return data

@deprecated_parameters(ParameterRename(old_name="n_jobs", new_name="workers", when="v2.0.0"))
def renamed(data: list, *, workers: int = 1) -> int:
    return workers

@deprecated_parameters(ParameterPositional(name="workers", old_index=1, when="v2.0.0"))
def positional(data: list, *, workers: int = 1) -> int:
    return workers

@deprecated_parameters(ParameterValueRemove(name="method", old_value="old_algo", new_value="new_algo"))
def valued(data: list, *, method: str = "new_algo") -> str:
    return method

class Cls:
    @deprecated_parameters(ParameterRemove(old_name="verbose"))
    def method(self, data: list) -> list:
        return data
"""

deprecated_calls = """
from stubbed import removed, renamed, positional, valued
removed([1], verbose=True)
renamed([1], n_jobs=4)
positional([1], 4)
valued([1], method="old_algo")
"""

clean_calls = """
from stubbed import removed, renamed, positional, valued
removed([1])
renamed([1], workers=4)
positional([1], workers=4)
valued([1], method="new_algo")
"""


@pytest.fixture(scope="module")
def stub_dir():
    original_cwd = os.getcwd()
    original_path = list(sys.path)
    with tempfile.TemporaryDirectory(prefix="_stubgen") as tmpdirname:
        os.chdir(tmpdirname)
        Path("stubbed.py").write_text(module_source)
        sys.path.insert(0, tmpdirname)
        Path("mypy.ini").write_text(make_mypy_ini(enable_error_code="deprecated"))
        yield tmpdirname
        os.chdir(original_cwd)
        sys.path[:] = original_path
        sys.modules.pop("stubbed", None)


def test_generated_stub_contains_overloads(stub_dir):
    stub = generate_stub("stubbed")
    assert "@overload" in stub
    assert "@deprecated(" in stub
    assert "from typing_extensions import deprecated" in stub
    assert "def removed(data: list, *, verbose: Any) -> list: ..." in stub
    assert "def renamed(data: list, *, n_jobs: int) -> int: ..." in stub
    assert "def positional(data: list, workers: int, /) -> int: ..." in stub
    assert "def valued(data: list, *, method: Literal['old_algo']) -> str: ..." in stub


def test_generated_stub_covers_methods(stub_dir):
    stub = generate_stub("stubbed")
    assert "class Cls:" in stub
    assert "    def method(self, data: list, *, verbose: Any) -> list: ..." in stub


def test_generated_stub_is_not_self_referential(stub_dir):
    assert "from stubbed import *" not in generate_stub("stubbed")


def test_module_without_deprecations_yields_nothing(stub_dir):
    Path("plain.py").write_text("def f(a: int) -> int:\n    return a\n")
    assert generate_stub("plain") == ""


def run_mypy(source, name):
    from mypy import api

    Path(name).write_text(source)
    out, err, code = api.run(["--config-file", "mypy.ini", name])
    assert not err, f"mypy errored out:\n{err}"
    assert out, f"mypy produced no output, exit code {code}"
    return out, code


def test_type_checker_reports_the_deprecated_calls(stub_dir):
    Path("stubbed.pyi").write_text(generate_stub("stubbed"))
    out, code = run_mypy(deprecated_calls, "deprecated_calls.py")
    assert out.count("[deprecated]") == 4, out
    assert "call-overload" not in out, out
    assert code == 1


def test_type_checker_accepts_the_clean_calls(stub_dir):
    Path("stubbed.pyi").write_text(generate_stub("stubbed"))
    out, code = run_mypy(clean_calls, "clean_calls.py")
    assert "deprecated" not in out, out
    assert "Success" in out, out
    assert code == 0


def test_main_writes_to_a_file(stub_dir):
    assert main(["stubbed", "-o", "out.pyi"]) == 0
    assert "@overload" in Path("out.pyi").read_text()


def test_main_reports_when_there_is_nothing(stub_dir, capsys):
    Path("empty.py").write_text("x = 1\n")
    assert main(["empty"]) == 1
    assert "No deprecated parameters found" in capsys.readouterr().err


def test_console_script(stub_dir):
    script = Path(sys.executable).parent / "deprecated-parameters-stubgen"
    if not script.exists():  # pragma: no cover
        pytest.skip("the package is not installed, so its entry point is not available")
    result = subprocess.run(
        [str(script), "stubbed"],
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONPATH": stub_dir},
    )
    assert result.returncode == 0, result.stderr
    assert "@overload" in result.stdout


def test_positional_overloads_follow_old_index(stub_dir):
    Path("ordered.py").write_text(
        "from deprecated_parameters import deprecated_parameters, ParameterPositional\n"
        "@deprecated_parameters(\n"
        '    ParameterPositional(name="flag", old_index=2),\n'
        '    ParameterPositional(name="workers", old_index=1),\n'
        ")\n"
        'def compute(data: list, *, workers: int = 1, flag: str = "x") -> int:\n'
        "    return workers\n"
    )
    stub = generate_stub("ordered")
    assert "def compute(data: list, workers: int, /, *, flag: str = ...) -> int: ..." in stub
    assert "def compute(data: list, workers: int, flag: str, /) -> int: ..." in stub


removed_positional_source = """
from deprecated_parameters import deprecated_parameters, ParameterRemove

@deprecated_parameters(ParameterRemove(old_name="verbose", old_index=2))
def compute(data: list, workers: int = 1) -> int:
    return workers
"""

removed_positional_calls = """
from removed_positional import compute
compute([1], 4, True)
compute([1], verbose=True)
compute([1], 4)
"""


def test_removal_overload_covers_the_old_position(stub_dir):
    Path("removed_positional.py").write_text(removed_positional_source)
    stub = generate_stub("removed_positional")
    assert "def compute(data: list, workers: int = ..., *, verbose: Any) -> int: ..." in stub
    assert "def compute(data: list, workers: int, verbose: Any, /) -> int: ..." in stub


def test_removal_overloads_are_reported_by_a_type_checker(stub_dir):
    Path("removed_positional.py").write_text(removed_positional_source)
    Path("removed_positional.pyi").write_text(generate_stub("removed_positional"))
    out, code = run_mypy(removed_positional_calls, "removed_positional_calls.py")
    assert out.count("[deprecated]") == 2, out
    assert "call-overload" not in out, out
    assert code == 1


removed_kept_source = """
from deprecated_parameters import deprecated_parameters, ParameterRemove

@deprecated_parameters(ParameterRemove(old_name="verbose", transform=None))
def compute(data: list, verbose: bool = False) -> int:
    return 1
"""

removed_kept_calls = """
from removed_kept import compute
compute([1], verbose=True)
compute([1])
"""


def test_removal_without_transform_keeps_the_parameter_once(stub_dir):
    Path("removed_kept.py").write_text(removed_kept_source)
    stub = generate_stub("removed_kept")
    # The parameter is still in the signature, so the overload only makes it required.
    assert "def compute(data: list, verbose: bool) -> int: ..." in stub
    assert "*, verbose" not in stub


def test_removal_without_transform_produces_a_valid_stub(stub_dir):
    Path("removed_kept.py").write_text(removed_kept_source)
    Path("removed_kept.pyi").write_text(generate_stub("removed_kept"))
    out, code = run_mypy(removed_kept_calls, "removed_kept_calls.py")
    assert out.count("[deprecated]") == 1, out
    assert "duplicate" not in out.lower(), out
    assert code == 1


def test_positional_overload_makes_the_preceding_arguments_required(stub_dir):
    Path("optional_leading.py").write_text(
        "from deprecated_parameters import deprecated_parameters, ParameterPositional\n"
        "@deprecated_parameters(ParameterPositional(name='workers', old_index=1))\n"
        "def compute(data: list = [], *, workers: int = 1) -> int:\n"
        "    return workers\n"
    )
    stub = generate_stub("optional_leading")
    # A default before a required argument would not even be valid syntax.
    assert "def compute(data: list, workers: int, /) -> int: ..." in stub
