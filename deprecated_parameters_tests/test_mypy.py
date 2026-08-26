import os
import site
import sysconfig
import tempfile
from pathlib import Path

import pytest

import deprecated_parameters

pytest.importorskip("mypy", reason="mypy not installed")


def get_mypy_path() -> str:
    """Directory that contains the ``deprecated_parameters`` package, for mypy to be able to find it.

    Needed because mypy cannot resolve PEP 660 editable installs, which is what ``pip install -e .``
    creates. When the package is installed normally mypy finds it on its own, and giving it a site-packages
    directory in ``mypy_path`` is an error.
    """
    package_path = Path(deprecated_parameters.__file__).parent.parent.resolve()
    site_paths = {Path(p).resolve() for p in site.getsitepackages()}
    site_paths.add(Path(site.getusersitepackages()).resolve())
    site_paths.add(Path(sysconfig.get_path("purelib")).resolve())
    return "" if package_path in site_paths else str(package_path)


mypy_path = get_mypy_path()


def make_mypy_ini(**settings: str) -> str:
    """Build a mypy configuration, only setting mypy_path when it is actually needed."""
    lines = ["[mypy]", "follow_imports = silent"]
    if mypy_path:
        lines.append(f"mypy_path = {mypy_path}")
    lines.extend(f"{name} = {value}" for name, value in settings.items())
    return "\n".join(lines) + "\n"


mypy_ini = make_mypy_ini(plugins="deprecated_parameters:mypy_plugin")


@pytest.fixture(scope="session")
def cache_dir():
    original_cwd = os.getcwd()
    with tempfile.TemporaryDirectory(prefix=f"_{__name__}") as tmpdirname:
        os.chdir(tmpdirname)
        Path("mypy.ini").write_text(mypy_ini)
        yield tmpdirname
        os.chdir(original_cwd)


def run_mypy(source):
    from mypy import api

    imports = (
        "from deprecated_parameters import deprecated_parameters, ParameterRemove, ParameterRename, "
        "ParameterPositional, ParameterValueRemove"
    )
    source = imports + "\n" + source
    Path("test.py").write_text(source)
    out, err, code = api.run(["--config-file", "mypy.ini", "test.py"])
    assert not err, f"mypy errored out:\n{err}"
    assert out, f"mypy produced no output, exit code {code}"
    assert "import-not-found" not in out, f"mypy could not import deprecated_parameters:\n{out}"
    return out, code


func_keyword_parameter_remove = """
@deprecated_parameters(
    ParameterRemove(old_name="removed"),
)
def func_keyword_parameter_remove():
    pass

func_keyword_parameter_remove(removed=1)
"""


def test_keyword_parameter_remove(cache_dir):
    out, code = run_mypy(func_keyword_parameter_remove)
    assert 'error: Argument "removed" for "func_keyword_parameter_remove" is deprecated' in out
    assert code == 1


func_keyword_parameter_rename = """
@deprecated_parameters(
    ParameterRename(old_name="before", new_name="now"),
)
def func_keyword_parameter_rename(*, now: int):
    return now

func_keyword_parameter_rename(before=7)
"""


def test_keyword_parameter_rename(cache_dir):
    out, code = run_mypy(func_keyword_parameter_rename)
    assert 'error: Argument "before" for "func_keyword_parameter_rename" is deprecated' in out
    assert 'it has been renamed to "now" and "before" will no longer be accepted in the future' in out
    assert code == 1


# Deprecated names must not additionally be reported as unexpected keyword arguments. The plugin is
# expected to widen the signature so that the only error reported is the deprecation itself.


func_rename_no_call_arg = """
@deprecated_parameters(
    ParameterRename(old_name="before", new_name="now"),
)
def func_rename_no_call_arg(*, now: int = 0) -> int:
    return now

func_rename_no_call_arg(before=7)
"""


def test_rename_does_not_report_call_arg(cache_dir):
    out, code = run_mypy(func_rename_no_call_arg)
    assert 'error: Argument "before" for "func_rename_no_call_arg" is deprecated' in out
    assert "call-arg" not in out
    assert "Found 1 error" in out
    assert code == 1


func_remove_no_call_arg = """
@deprecated_parameters(
    ParameterRemove(old_name="removed"),
)
def func_remove_no_call_arg() -> None:
    pass

func_remove_no_call_arg(removed=1)
"""


def test_remove_does_not_report_call_arg(cache_dir):
    out, code = run_mypy(func_remove_no_call_arg)
    assert 'error: Argument "removed" for "func_remove_no_call_arg" is deprecated' in out
    assert "call-arg" not in out
    assert "Found 1 error" in out
    assert code == 1


# The renamed parameter keeps the type of the parameter it was renamed to.


func_rename_keeps_type = """
@deprecated_parameters(
    ParameterRename(old_name="before", new_name="now"),
)
def func_rename_keeps_type(*, now: int = 0) -> int:
    return now

func_rename_keeps_type(before="not an int")
"""


def test_rename_keeps_type_of_new_parameter(cache_dir):
    out, code = run_mypy(func_rename_keeps_type)
    assert 'error: Argument "before" for "func_rename_keeps_type" is deprecated' in out
    assert "arg-type" in out
    assert code == 1


# Methods, not only functions and constructors.


method_keyword_parameter_remove = """
class Cls:
    @deprecated_parameters(
        ParameterRemove(old_name="removed"),
    )
    def method_keyword_parameter_remove(self) -> None:
        pass

Cls().method_keyword_parameter_remove(removed=1)
"""


def test_method_keyword_parameter_remove(cache_dir):
    out, code = run_mypy(method_keyword_parameter_remove)
    assert 'error: Argument "removed" for "method_keyword_parameter_remove" is deprecated' in out
    assert "call-arg" not in out
    assert code == 1


method_keyword_parameter_rename = """
class Cls:
    @deprecated_parameters(
        ParameterRename(old_name="before", new_name="now"),
    )
    def method_keyword_parameter_rename(self, *, now: int = 0) -> int:
        return now

Cls().method_keyword_parameter_rename(before=2)
"""


def test_method_keyword_parameter_rename(cache_dir):
    out, code = run_mypy(method_keyword_parameter_rename)
    assert 'error: Argument "before" for "method_keyword_parameter_rename" is deprecated' in out
    assert 'it has been renamed to "now"' in out
    assert "call-arg" not in out
    assert code == 1


# Constructors, which are reached through a different node in the mypy AST.


init_keyword_parameter_remove = """
class Cls:
    @deprecated_parameters(
        ParameterRemove(old_name="removed"),
    )
    def __init__(self) -> None:
        pass

Cls(removed=1)
"""


def test_init_keyword_parameter_remove(cache_dir):
    out, code = run_mypy(init_keyword_parameter_remove)
    assert 'error: Argument "removed" for "Cls" is deprecated' in out
    assert "call-arg" not in out
    assert code == 1


# Calls in a module other than the one where the deprecation is declared.


cross_module_lib = """
from deprecated_parameters import deprecated_parameters, ParameterRemove, ParameterRename

@deprecated_parameters(
    ParameterRemove(old_name="removed"),
)
def lib_func() -> None:
    pass

class LibCls:
    @deprecated_parameters(
        ParameterRename(old_name="before", new_name="now"),
    )
    def lib_meth(self, *, now: int = 0) -> int:
        return now
"""

cross_module_use = """
from cross_module_lib import lib_func, LibCls
lib_func(removed=1)
LibCls().lib_meth(before=2)
"""


def test_cross_module_calls(cache_dir):
    Path("cross_module_lib.py").write_text(cross_module_lib)
    out, code = run_mypy(cross_module_use)
    assert 'error: Argument "removed" for "lib_func" is deprecated' in out
    assert 'error: Argument "before" for "lib_meth" is deprecated' in out
    assert "call-arg" not in out
    assert code == 1


# Calls that do not use a deprecated parameter must not be reported.


func_no_deprecated_argument = """
@deprecated_parameters(
    ParameterRename(old_name="before", new_name="now"),
)
def func_no_deprecated_argument(*, now: int = 0) -> int:
    return now

func_no_deprecated_argument(now=1)
"""


def test_no_error_when_deprecated_parameter_unused(cache_dir):
    out, code = run_mypy(func_no_deprecated_argument)
    assert "deprecated-arg" not in out
    assert "Success" in out
    assert code == 0


# ---------------------------------------------------------------- ParameterPositional

positional_keyword = """
@deprecated_parameters(
    ParameterPositional(name="workers", old_index=1, when="v2.0.0"),
)
def compute(data: list, *, workers: int = 1) -> int:
    return workers

compute([1], 4)
"""


def test_positional_reported_and_signature_widened(cache_dir):
    out, code = run_mypy(positional_keyword)
    assert 'error: Giving argument "workers" for "compute" positionally is deprecated' in out
    assert "must be given as a keyword argument in v2.0.0" in out
    assert "Too many positional arguments" not in out
    assert "Found 1 error" in out
    assert code == 1


positional_keyword_ok = """
@deprecated_parameters(
    ParameterPositional(name="workers", old_index=1, when="v2.0.0"),
)
def compute(data: list, *, workers: int = 1) -> int:
    return workers

compute([1], workers=4)
"""


def test_positional_keyword_call_not_reported(cache_dir):
    out, code = run_mypy(positional_keyword_ok)
    assert "deprecated-arg" not in out
    assert "Success" in out
    assert code == 0


positional_keeps_type = """
@deprecated_parameters(
    ParameterPositional(name="workers", old_index=1),
)
def compute(data: list, *, workers: int = 1) -> int:
    return workers

compute([1], "not an int")
"""


def test_positional_widened_argument_keeps_its_type(cache_dir):
    out, code = run_mypy(positional_keeps_type)
    assert "deprecated-arg" in out
    assert "arg-type" in out
    assert code == 1


positional_no_transform = """
@deprecated_parameters(
    ParameterPositional(name="workers", old_index=1, transform=None),
)
def compute(data: list, workers: int = 1) -> int:
    return workers

compute([1], 4)
compute([1], workers=4)
"""


def test_positional_no_transform_reported_only_when_positional(cache_dir):
    out, code = run_mypy(positional_no_transform)
    assert out.count("deprecated-arg") == 1
    assert "test.py:9" in out  # the positional call, not the keyword one on the next line
    assert code == 1


# ---------------------------------------------------------------- ParameterValueRemove

value_keyword = """
@deprecated_parameters(
    ParameterValueRemove(name="method", old_value="old_algo", new_value="new_algo", when="v2.0.0"),
)
def compute(data: list, *, method: str = "new_algo") -> str:
    return method

compute([1], method="old_algo")
"""


def test_value_reported(cache_dir):
    out, code = run_mypy(value_keyword)
    assert 'error: Value \'old_algo\' for argument "method" of "compute" is deprecated' in out
    assert "use 'new_algo' instead" in out
    assert code == 1


value_not_deprecated = """
@deprecated_parameters(
    ParameterValueRemove(name="method", old_value="old_algo", new_value="new_algo"),
)
def compute(data: list, *, method: str = "new_algo") -> str:
    return method

compute([1], method="new_algo")
compute([1])
"""


def test_value_not_reported_for_other_values(cache_dir):
    out, code = run_mypy(value_not_deprecated)
    assert "deprecated-arg" not in out
    assert "Success" in out
    assert code == 0


value_positional = """
@deprecated_parameters(
    ParameterValueRemove(name="method", old_value="old_algo", new_value="new_algo"),
)
def compute(data: list, method: str = "new_algo") -> str:
    return method

compute([1], "old_algo")
"""


def test_value_reported_when_given_positionally(cache_dir):
    out, code = run_mypy(value_positional)
    assert "deprecated-arg" in out
    assert code == 1


value_non_literal = """
@deprecated_parameters(
    ParameterValueRemove(name="method", old_value="old_algo", new_value="new_algo"),
)
def compute(data: list, *, method: str = "new_algo") -> str:
    return method

variable = "old_algo"
compute([1], method=variable)
"""


def test_value_not_reported_for_non_literal(cache_dir):
    out, code = run_mypy(value_non_literal)
    assert "deprecated-arg" not in out
    assert code == 0


value_int_and_bool = """
@deprecated_parameters(
    ParameterValueRemove(name="jobs", old_value=-1, new_value=1),
    ParameterValueRemove(name="flag", old_value=True, new_value=False),
)
def compute(data: list, *, jobs: int = 1, flag: bool = False) -> int:
    return jobs

compute([1], jobs=-1, flag=True)
"""


def test_value_reported_for_int_and_bool_literals(cache_dir):
    out, code = run_mypy(value_int_and_bool)
    assert out.count("deprecated-arg") == 2
    assert code == 1


# ---------------------------------------------------------------- version in the reported message

version_message = """
@deprecated_parameters(
    ParameterRemove(old_name="verbose", version="1.5.0", when="v2.0.0"),
)
def compute(data: list) -> list:
    return data

compute([1], verbose=True)
"""


def test_version_included_in_reported_message(cache_dir):
    out, code = run_mypy(version_message)
    assert 'Argument "verbose" for "compute" is deprecated since 1.5.0' in out
    assert code == 1


# Writing the signature as it will be means narrowing the annotation, which must not then be reported
# as an incompatible argument type on top of the deprecation.


value_narrowed_literal = """
from typing import Literal

@deprecated_parameters(
    ParameterValueRemove(name="method", old_value="old_algo", new_value="new_algo"),
)
def compute(data: list, *, method: Literal["new_algo"] = "new_algo") -> str:
    return method

compute([1], method="old_algo")
"""


def test_value_with_narrowed_literal_is_not_also_an_arg_type_error(cache_dir):
    out, code = run_mypy(value_narrowed_literal)
    assert 'Value \'old_algo\' for argument "method" of "compute" is deprecated' in out
    assert "arg-type" not in out
    assert "Found 1 error" in out
    assert code == 1


value_narrowed_literal_other_value = """
from typing import Literal

@deprecated_parameters(
    ParameterValueRemove(name="method", old_value="old_algo", new_value="new_algo"),
)
def compute(data: list, *, method: Literal["new_algo"] = "new_algo") -> str:
    return method

compute([1], method="never_valid")
"""


def test_widening_still_rejects_values_that_were_never_valid(cache_dir):
    out, code = run_mypy(value_narrowed_literal_other_value)
    assert "arg-type" in out
    assert "deprecated-arg" not in out
    assert code == 1


value_narrowed_int = """
from typing import Literal

@deprecated_parameters(
    ParameterValueRemove(name="jobs", old_value=-1, new_value=1),
)
def compute(data: list, *, jobs: Literal[1, 2] = 1) -> int:
    return jobs

compute([1], jobs=-1)
"""


def test_value_widening_for_int_literals(cache_dir):
    out, code = run_mypy(value_narrowed_int)
    assert "deprecated-arg" in out
    assert "arg-type" not in out
    assert code == 1


positional_out_of_order = """
@deprecated_parameters(
    ParameterPositional(name="flag", old_index=2),
    ParameterPositional(name="workers", old_index=1),
)
def compute(data: list, *, workers: int = 1, flag: str = "x") -> int:
    return workers

compute([1], 4, "y")
compute([1], 4)
compute([1], "wrong")
"""


def test_positional_reported_by_old_index_not_declaration_order(cache_dir):
    out, code = run_mypy(positional_out_of_order)
    lines = [line for line in out.splitlines() if "deprecated-arg" in line]
    assert len(lines) == 4
    # Both are reported for the call giving both positionally, workers alone for the next one.
    assert sum(1 for line in lines if line.startswith("test.py:10")) == 2
    assert sum(1 for line in lines if line.startswith("test.py:11")) == 1
    # The widened argument keeps the type it has as a keyword argument.
    assert 'Argument 2 to "compute" has incompatible type "str"; expected "int"' in out
    assert code == 1


remove_old_index = """
@deprecated_parameters(
    ParameterRemove(old_name="verbose", old_index=2),
)
def compute(data: list, workers: int = 1) -> int:
    return workers

compute([1], 4, True)
compute([1], 4)
compute([1], verbose=True)
"""


def test_remove_reported_when_given_positionally(cache_dir):
    out, code = run_mypy(remove_old_index)
    lines = [line for line in out.splitlines() if "deprecated-arg" in line]
    assert len(lines) == 2
    assert lines[0].startswith("test.py:9")  # the old style call
    assert lines[1].startswith("test.py:11")  # the keyword form, still reported
    assert "its value is ignored" in lines[0]
    # The extra argument must not additionally be reported as unexpected.
    assert "Too many arguments" not in out
    assert "call-arg" not in out
    assert code == 1


remove_old_index_with_positional = """
@deprecated_parameters(
    ParameterRemove(old_name="verbose", old_index=2),
    ParameterPositional(name="workers", old_index=1),
)
def compute(data: list, *, workers: int = 1) -> int:
    return workers

compute([1], 4, True)
"""


def test_remove_and_positional_share_the_old_positions(cache_dir):
    out, code = run_mypy(remove_old_index_with_positional)
    lines = [line for line in out.splitlines() if "deprecated-arg" in line]
    assert len(lines) == 2
    assert all(line.startswith("test.py:10") for line in lines)
    assert "call-arg" not in out
    assert 'Argument 2 to "compute" has incompatible type' not in out
    assert code == 1
