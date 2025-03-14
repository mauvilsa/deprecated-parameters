import warnings

import pytest

from deprecated_parameters import deprecated_parameters, ParameterRemove, ParameterRename


def test_parameter_remove_missing_required():
    with pytest.raises(TypeError, match="missing 1 required keyword-only argument: 'old_name'"):
        ParameterRemove()


def test_parameter_rename_missing_required():
    with pytest.raises(TypeError, match="missing 1 required keyword-only argument: 'new_name'"):
        ParameterRename(old_name="old_name")


def test_deprecated_parameters_decorator_positional_only():
    with pytest.raises(TypeError, match="deprecated_parameters.. got an unexpected keyword argument"):
        @deprecated_parameters(deprecations=[])
        def func_positional_only():
            pass


def test_deprecated_parameters_decorator_empty():
    with pytest.raises(ValueError, match="At least one deprecation must be provided"):
        @deprecated_parameters()
        def func_decorator_empty():
            pass


def test_deprecated_parameters_decorator_multiple():
    with pytest.raises(ValueError, match="@deprecated_parameters decorator can only be applied once per callable"):
        @deprecated_parameters(
            ParameterRemove(old_name="old_name"),
        )
        @deprecated_parameters(
            ParameterRename(old_name="old_name", new_name="new_name"),
        )
        def func_decorator_multiple(new_name: str):
            pass


@deprecated_parameters(
    ParameterRemove(old_name="removed"),
)
def func_keyword_parameter_remove():
    pass


def test_func_keyword_parameter_remove():
    with warnings.catch_warnings(record=True) as w:
        func_keyword_parameter_remove(removed=1)
    assert len(w) == 1
    assert issubclass(w[-1].category, DeprecationWarning)
    assert 'Argument "removed" to "func_keyword_parameter_remove" is deprecated ' in str(w[-1].message)

    with warnings.catch_warnings(record=True) as w:
        func_keyword_parameter_remove()
    assert len(w) == 0


@deprecated_parameters(
    ParameterRename(old_name="before", new_name="now"),
)
def func_keyword_parameter_rename(*, now: int):
    return now


def test_func_keyword_parameter_rename():
    with warnings.catch_warnings(record=True) as w:
        assert func_keyword_parameter_rename(before=7) == 7
    assert len(w) == 1
    assert issubclass(w[-1].category, DeprecationWarning)
    assert 'Argument "before" to "func_keyword_parameter_rename" is deprecated' in str(w[-1].message)
    assert 'it has been renamed to "now" and "before" will be removed in the future' in str(w[-1].message)

    with warnings.catch_warnings(record=True) as w:
        assert func_keyword_parameter_rename(now=6) == 6
    assert len(w) == 0


class KeywordParameterRemove:
    @deprecated_parameters(
        ParameterRemove(old_name="removed"),
    )
    def method_keyword_parameter_remove(self):
        pass


def test_method_keyword_parameter_remove():
    instance = KeywordParameterRemove()

    with warnings.catch_warnings(record=True) as w:
        instance.method_keyword_parameter_remove(removed=1)
    assert len(w) == 1
    assert issubclass(w[-1].category, DeprecationWarning)
    assert 'Argument "removed" to "method_keyword_parameter_remove" is deprecated' in str(w[-1].message)

    with warnings.catch_warnings(record=True) as w:
        instance.method_keyword_parameter_remove()
    assert len(w) == 0


class KeywordParameterRename:
    @deprecated_parameters(
        ParameterRename(old_name="before", new_name="now"),
    )
    def method_keyword_parameter_rename(self, *, now: int):
        return now


def test_method_keyword_parameter_rename():
    instance = KeywordParameterRename()

    with warnings.catch_warnings(record=True) as w:
        assert instance.method_keyword_parameter_rename(before=9) == 9
    assert len(w) == 1
    assert issubclass(w[-1].category, DeprecationWarning)
    assert 'Argument "before" to "method_keyword_parameter_rename" is deprecated' in str(w[-1].message)
    assert 'it has been renamed to "now" and "before" will be removed in the future' in str(w[-1].message)

    with warnings.catch_warnings(record=True) as w:
        assert instance.method_keyword_parameter_rename(now=8) == 8
    assert len(w) == 0
