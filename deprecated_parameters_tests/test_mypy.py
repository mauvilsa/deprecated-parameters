import os
import tempfile
from importlib.util import find_spec
from pathlib import Path

import pytest


@pytest.fixture
def mypy_plugin():
    if not find_spec("mypy"):
        pytest.skip("mypy not installed")


mypy_ini = """
[mypy]
plugins = deprecated_parameters:mypy_plugin
"""


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

    source = "from deprecated_parameters import deprecated_parameters, ParameterRemove, ParameterRename" + "\n" + source
    Path("test.py").write_text(source)
    out, _, code = api.run(["--config-file", "mypy.ini", "test.py"])
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
    assert 'it has been renamed to "now" and "before" will be removed in the future' in out
    assert code == 1
