import sys
import types
import warnings

import pytest

from deprecated_parameters import (
    ParameterPositional,
    ParameterRemove,
    ParameterRename,
    ParameterValueRemove,
    deprecated_parameters,
)
from deprecated_parameters._sphinx import documenting, sphinx_build_modules


@pytest.fixture
def sphinx_build(monkeypatch):
    """Make the package believe that sphinx is building, as it is when autodoc imports a module."""
    for module in sphinx_build_modules:
        monkeypatch.setitem(sys.modules, module, types.ModuleType(module))
    assert documenting()


@pytest.fixture
def documented(sphinx_build):
    @deprecated_parameters(
        ParameterRemove(old_name="verbose", version="1.5.0", when="v2.0.0"),
    )
    def func(data, **kwargs):
        """Compute things.

        Args:
            data: the data.
        """
        return data

    return func


# ---------------------------------------------------------------- auto activation


def test_not_documented_outside_a_sphinx_build():
    for module in sphinx_build_modules:
        assert module not in sys.modules

    @deprecated_parameters(ParameterRemove(old_name="verbose"))
    def func(data, **kwargs):
        """Compute things."""
        return data

    assert func.__doc__ == "Compute things."


def test_importing_sphinx_alone_does_not_activate(monkeypatch):
    monkeypatch.setitem(sys.modules, "sphinx", types.ModuleType("sphinx"))
    assert not documenting()


def test_documented_during_a_sphinx_build(sphinx_build):
    @deprecated_parameters(ParameterRemove(old_name="verbose"))
    def func(data, **kwargs):
        """Compute things."""
        return data

    assert func.__doc__.startswith("Compute things.")
    assert ".. deprecated::" in func.__doc__


def test_autodoc_alone_is_enough(monkeypatch):
    monkeypatch.setitem(sys.modules, "sphinx.ext.autodoc", types.ModuleType("sphinx.ext.autodoc"))
    assert documenting()


# ---------------------------------------------------------------- rendering


def test_directive_appended_to_docstring(documented):
    assert "Compute things." in documented.__doc__
    assert "Args:" in documented.__doc__
    assert ".. deprecated:: 1.5.0" in documented.__doc__
    assert 'Argument "verbose" for "func" is deprecated since 1.5.0' in documented.__doc__


def test_directive_indented_like_the_docstring_body(documented):
    # From python 3.13 docstrings are dedented by the compiler, so the body indent is empty there.
    lines = documented.__doc__.splitlines()
    body = next(line for line in lines if line.strip() == "Args:")
    directive = next(line for line in lines if ".. deprecated::" in line)
    indent = body[: len(body) - len(body.lstrip())]
    assert directive == f"{indent}.. deprecated:: 1.5.0"


def test_decorator_still_warns_at_runtime(documented):
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        documented([1], verbose=True)
    assert len(w) == 1


def test_docstring_created_when_missing(sphinx_build):
    @deprecated_parameters(ParameterRemove(old_name="verbose"))
    def bare(data, **kwargs):
        return data

    assert bare.__doc__ is not None
    assert bare.__doc__.startswith(".. deprecated::")


def test_one_directive_per_deprecation(sphinx_build):
    @deprecated_parameters(
        ParameterRemove(old_name="a", version="1.0.0"),
        ParameterRemove(old_name="b", version="2.0.0"),
        ParameterRemove(old_name="c", version="1.0.0"),
    )
    def several(data, **kwargs):
        return data

    assert several.__doc__.count(".. deprecated:: 1.0.0") == 2
    assert several.__doc__.count(".. deprecated:: 2.0.0") == 1


def test_directives_are_separated_by_a_blank_line(sphinx_build):
    @deprecated_parameters(
        ParameterRemove(old_name="a", version="1.0.0"),
        ParameterRemove(old_name="b", version="1.0.0"),
    )
    def several(data, **kwargs):
        return data

    assert '"a"' in several.__doc__ and '"b"' in several.__doc__
    assert "\n\n.. deprecated:: 1.0.0" in several.__doc__


def test_when_used_as_the_version_when_not_given(sphinx_build):
    @deprecated_parameters(ParameterRemove(old_name="a", when="v9.0.0"))
    def func(data, **kwargs):
        return data

    assert ".. deprecated:: v9.0.0" in func.__doc__


def test_all_deprecation_kinds_documented(sphinx_build):
    @deprecated_parameters(
        ParameterRemove(old_name="r"),
        ParameterRename(old_name="o", new_name="n"),
        ParameterPositional(name="p", old_index=1),
        ParameterValueRemove(name="v", old_value=1, new_value=2),
    )
    def every(data, *, n=None, p=None, v=2, **kwargs):
        return data

    for fragment in ['Argument "r"', 'Argument "o"', 'argument "p"', 'argument "v"']:
        assert fragment in every.__doc__


def test_long_message_is_not_wrapped(sphinx_build):
    # Sphinx reflows the text, so the message stays on one line however long it is.
    @deprecated_parameters(
        ParameterRemove(old_name="verbose", when="a really quite long removal horizon indeed"),
    )
    def func(data, **kwargs):
        return data

    body = [line for line in func.__doc__.splitlines() if ".. deprecated::" not in line and line.strip()]
    assert len(body) == 1
    assert len(body[0]) > 88


def test_directive_body_is_indented(sphinx_build):
    @deprecated_parameters(ParameterRemove(old_name="verbose"))
    def func(data, **kwargs):
        return data

    body = [line for line in func.__doc__.splitlines() if ".. deprecated::" not in line and line.strip()]
    assert all(line.startswith("   ") for line in body)


def test_multiline_custom_message_stays_indented(sphinx_build):
    @deprecated_parameters(
        ParameterRemove(old_name="verbose", message="%(old_name)s is gone.\nUse logging instead."),
    )
    def func(data, **kwargs):
        return data

    body = [line for line in func.__doc__.splitlines() if ".. deprecated::" not in line and line.strip()]
    assert body == ["   verbose is gone.", "   Use logging instead."]
