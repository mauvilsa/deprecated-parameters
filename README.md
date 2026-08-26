[![PyPI version](https://img.shields.io/pypi/v/deprecated-parameters.svg)](https://pypi.org/project/deprecated-parameters)
[![Python versions](https://img.shields.io/pypi/pyversions/deprecated-parameters.svg)](https://pypi.org/project/deprecated-parameters)
[![tests](https://github.com/mauvilsa/deprecated-parameters/actions/workflows/tests.yaml/badge.svg)](https://github.com/mauvilsa/deprecated-parameters/actions/workflows/tests.yaml)

# deprecated-parameters

Deprecation of parameters in function and method signatures, reported both at
runtime and by [mypy](https://mypy-lang.org).

Python has a standard way to deprecate an entire function, method or class,
`warnings.deprecated` from [PEP 702](https://peps.python.org/pep-0702/). It
deliberately does not cover *individual parameters*, and the PEP explicitly
rejected a `Deprecated[type, message]` modifier for that purpose. As a result,
every large project ends up writing its own decorator, for example
`pandas.util._decorators.deprecate_kwarg`,
`astropy.utils.decorators.deprecated_renamed_argument` and
`twisted.python.deprecate.deprecatedKeywordParameter`. They are all private, and
none of them are understood by a type checker.

This package provides a single reusable decorator for the same purpose, and a
mypy plugin so that misuse is reported statically, before the code runs.

## Installation

```bash
pip install deprecated-parameters
```

To also install mypy, so that deprecated parameters are reported statically:

```bash
pip install deprecated-parameters[mypy]
```

## Usage

### Removing a parameter

Take the parameter out of the signature and declare it with `ParameterRemove`.
The function is then written the way it will stay, without the parameter and
without anything to handle it. Callers that still give it get a
`DeprecationWarning` instead of a `TypeError`, and the value they give is
dropped, which is what the warning tells them:

```python
from deprecated_parameters import deprecated_parameters, ParameterRemove

@deprecated_parameters(
    ParameterRemove(old_name="verbose", when="v2.0.0"),
)
def compute(data):
    return data

compute([1], verbose=True)
# DeprecationWarning: Argument "verbose" for "compute" is deprecated, its value
# is ignored and it will no longer be accepted in v2.0.0
```

Only the keyword form is recognized this way. For a parameter that callers could
also give positionally, add `old_index`, the position it had in the previous
signature:

```python
# The previous signature was compute(data, workers, verbose).
@deprecated_parameters(
    ParameterRemove(old_name="verbose", old_index=2, when="v2.0.0"),
)
def compute(data, workers=1):
    return workers

compute([1], 4, True)  # returns 4, the extra argument is dropped
compute([1], 4)        # unchanged, no warning
```

`old_index` is zero based and counts every positional parameter, so `self` is
index 0 for methods. A removed parameter has to have been the *last* positional
one, otherwise an argument given for it cannot be told apart from one given for
the parameter that took its place, and the decorator says so when it is applied:

```python
# The previous signature was compute(data, verbose, workers), so an argument at
# position 1 could be either verbose or workers.
@deprecated_parameters(
    ParameterRemove(old_name="verbose", old_index=1),
)
def compute(data, workers=1):
    return workers
# ValueError: The old_index values of the parameters of compute that are no longer
# positional must be [2], got [1]. ...
```

To keep receiving the value instead of dropping it, see
[transform=None](#transforms-and-the-signature) below.

### Renaming a parameter

Rename the parameter in the signature and declare the old name with
`ParameterRename`. Callers that still use the old name get a
`DeprecationWarning`, and the value is forwarded to the new name.

```python
from deprecated_parameters import deprecated_parameters, ParameterRename

@deprecated_parameters(
    ParameterRename(old_name="n_jobs", new_name="workers", when="v2.0.0"),
)
def compute(data, *, workers: int = 1):
    return workers

compute([1], n_jobs=4)  # returns 4
# DeprecationWarning: Argument "n_jobs" for "compute" is deprecated, it has been
# renamed to "workers" and "n_jobs" will no longer be accepted in v2.0.0
```

Giving both the old and the new name in the same call raises a `ValueError`.

### Deprecating positional use of a parameter

To migrate a parameter to keyword-only, make it keyword-only in the signature and declare it with
`ParameterPositional`. Callers that still give it positionally get a `DeprecationWarning` instead of a
`TypeError`, and the value is moved to the keyword argument.

```python
from deprecated_parameters import deprecated_parameters, ParameterPositional

@deprecated_parameters(
    ParameterPositional(name="workers", old_index=1, when="v2.0.0"),
)
def compute(data, *, workers: int = 1):
    return workers

compute([1], 4)  # returns 4
# DeprecationWarning: Giving argument "workers" for "compute" positionally is deprecated,
# it must be given as a keyword argument in v2.0.0
```

`old_index` is the position the parameter had in the previous signature, zero based and counting every
positional parameter, so `self` is index 0 for methods. It is given explicitly rather than taken from
the order of the deprecations, so that reordering them can not silently change which argument goes
where. Applying the decorator fails when the indexes do not match the signature, and the error states
which ones are expected:

```python
@deprecated_parameters(
    ParameterPositional(name="flag", old_index=2),
    ParameterPositional(name="workers", old_index=1),
)
def compute(data, *, workers: int = 1, flag: str = "x"):
    return workers

compute([1], 4, "y")  # workers is 4 and flag is "y", whatever order they were declared in
```

To only warn while the parameter is still accepted positionally, use `transform=None` and leave the
signature unchanged. `old_index` is then the position it currently has.

### Deprecating one accepted value of a parameter

`ParameterValueRemove` removes a single value from the set a parameter accepts, leaving the parameter
itself in place. Drop the value from the annotation, and callers that still pass it get a warning and
have it replaced with `new_value`.

```python
from typing import Literal
from deprecated_parameters import deprecated_parameters, ParameterValueRemove

@deprecated_parameters(
    ParameterValueRemove(name="method", old_value="linear", new_value="lstsq", when="v2.0.0"),
)
def solve(data, *, method: Literal["lstsq", "qr"] = "qr"):
    return method

solve([1], method="linear")  # returns "lstsq"
# DeprecationWarning: Value 'linear' for argument "method" of "solve" is deprecated and
# will not be supported in v2.0.0, use 'lstsq' instead
```

This only ever looks at values the caller actually passes, whether by keyword or positionally. It is
not about defaults: omitting the argument never warns, regardless of what the default is.

For a value that is going away with nothing to replace it, simply do not give `new_value`. The
transform then has nothing to do, so the caller keeps receiving the deprecated value and only gets the
warning. `transform=None` is only needed to warn about a value that does have a replacement without
applying it.

### Several deprecations at once

The decorator accepts any number of deprecations, but can only be applied once
per callable.

```python
@deprecated_parameters(
    ParameterRemove(old_name="verbose"),
    ParameterRename(old_name="n_jobs", new_name="workers"),
)
def compute(data, *, workers: int = 1):
    return workers
```

### Transforms and the signature

The point of a transform is that the signature can already be written the way it
will stay once the deprecation period is over. `ParameterRemove` takes the
parameter out of it, `ParameterRename` renames it, `ParameterPositional` makes
it keyword-only and `ParameterValueRemove` drops a value from its annotation.
Calls that still use the old form are adapted to that signature, so they keep
working and only get a warning.

This is why the old form has to be gone from the signature. Declaring a
transform for a parameter that is still there raises a `ValueError` when the
decorator is applied.

`transform=None` is the opposite case: leave the signature as it is today and
only warn. Nothing about the call is changed, so the function receives exactly
what the caller passed, and the warning does not claim otherwise.

```python
@deprecated_parameters(
    ParameterRemove(old_name="verbose", transform=None),
)
def compute(data, verbose=False):
    return verbose  # the signature is unchanged, the call is only warned about

compute([1], verbose=True)
# DeprecationWarning: Argument "verbose" for "compute" is deprecated and will no
# longer be accepted in the future
```

Since nothing is changed, the function has to be able to receive the argument.
Either the parameter is still in the signature, as above, or the signature has a
`**kwargs` for it to land in:

```python
@deprecated_parameters(
    ParameterRemove(old_name="verbose", transform=None),
)
def compute(data, **kwargs):
    return kwargs  # {'verbose': True}
```

When it has neither, every call giving the parameter would warn and then fail
with a `TypeError`, so the decorator refuses it:

```python
@deprecated_parameters(
    ParameterRemove(old_name="verbose", transform=None),
)
def compute(data):
    return data
# ValueError: Parameter 'verbose' is not in the signature of compute and there is
# no **kwargs to receive it, so with transform=None every call giving it would
# fail. ...
```

#### Removing a parameter from a function that has `**kwargs`

A `**kwargs` in the signature does not change what `ParameterRemove` does: with
its transform the argument is dropped, and it never reaches `**kwargs`. Passing
it through instead would be wrong more often than right, since `**kwargs` is
usually there to forward arguments somewhere else, where a parameter this
function has removed has no business turning up. It would also make the transform
a no-op, indistinguishable from `transform=None`.

So the choice is yours to state explicitly, and it is the same choice in every
signature:

- `transform="remove"`, the default, for *the value is gone, the function does
  nothing with it any more*. The warning says that the value is ignored.
- `transform=None` for *the function still receives and handles it, this is only
  an announcement*, with the parameter or a `**kwargs` there to receive it.

### Customizing the message

`when` is a free form string describing when the parameter stops being accepted,
`"the future"` by default. For full control, `message` accepts a printf style
template with the `func`, `old_name`, `when` and, for renames, `new_name` keys:

```python
@deprecated_parameters(
    ParameterRemove(
        old_name="verbose",
        message='%(old_name)s is deprecated in %(func)s, use logging instead',
    ),
)
def compute(data):
    return data
```

`version` records the release in which the parameter was deprecated. It must be a valid
[PEP 440](https://peps.python.org/pep-0440/) version, is added to the default messages as
`deprecated since <version>`, and is available to custom messages as `%(version)s`:

```python
@deprecated_parameters(
    ParameterRemove(old_name="verbose", version="1.5.0", when="v2.0.0"),
)
def compute(data):
    return data

compute([1], verbose=True)
# DeprecationWarning: Argument "verbose" for "compute" is deprecated since 1.5.0, its
# value is ignored and it will no longer be accepted in v2.0.0
```

### Choosing the warning category

`DeprecationWarning` is only shown by default in `__main__`, so it is invisible to the users of a
library. Projects such as pandas use `FutureWarning` for deprecations aimed at end users. The category
is set per deprecation:

```python
@deprecated_parameters(
    ParameterRemove(old_name="verbose", category=FutureWarning),
)
def compute(data):
    return data
```

### Introspection

`get_deprecated_parameters` returns the deprecations of a callable, or `None` if
it has none:

```python
from deprecated_parameters import get_deprecated_parameters

deprecations = get_deprecated_parameters(compute)
[x.old_name for x in deprecations.removed]  # ['verbose']
```

## Static checking with mypy

Enable the plugin in your mypy configuration:

```ini
# mypy.ini
[mypy]
plugins = deprecated_parameters:mypy_plugin
```

or:

```toml
# pyproject.toml
[tool.mypy]
plugins = ["deprecated_parameters:mypy_plugin"]
```

Calls that use a deprecated parameter are then reported under the
`deprecated-arg` error code, with the same message as at runtime:

```text
example.py:9: error: Argument "n_jobs" for "compute" is deprecated, it has been
renamed to "workers" and "n_jobs" will no longer be accepted in v2.0.0  [deprecated-arg]
```

The plugin widens the signature so that the deprecated form is not additionally
reported as an unexpected keyword argument or as too many positional arguments,
and a renamed parameter keeps the type of the parameter it was renamed to. To downgrade the errors to warnings,
disable the error code with `--disable-error-code deprecated-arg`.

Functions, methods and constructors are supported, in the module where they are
declared and in modules that import them. All four deprecation kinds are reported, with deprecated
values detected when given as a literal.

## Static checking with other type checkers

Pyright, ty and pyrefly have no plugin system, so the mypy plugin cannot serve them. What they do
support is [PEP 702](https://peps.python.org/pep-0702/), `warnings.deprecated` applied to an individual
`@overload`. The `deprecated-parameters-stubgen` command renders the declared deprecations in that
form:

```bash
deprecated-parameters-stubgen mypackage.mymodule -o overloads.pyi
```

For each decorated callable it emits a deprecated overload taking the deprecated form as a *required*
argument, so that only calls using it match, followed by the real signature:

```python
@overload
@deprecated("Argument \"n_jobs\" for \"compute\" is deprecated, it has been renamed to \"workers\" ...")
def compute(data: list, *, n_jobs: int) -> int: ...
@overload
def compute(data: list, *, workers: int = ...) -> int: ...
```

The same is available programmatically as `generate_stub(module_name)`. Add the overloads above the
corresponding function in the module itself, or merge them into its stub file. They import `deprecated` from `warnings` on python 3.13 and later, and from `typing_extensions`
before that, so `typing_extensions` must be available to the type checker in that case.

## Documenting the deprecations with sphinx

While sphinx is building, and only then, the decorator also appends a `.. deprecated::` directive to the
docstring, one per deprecation, so that the deprecations appear in the built documentation. There is
nothing to enable and no second decorator to import, and outside of a build the docstring is untouched:

```python
from deprecated_parameters import deprecated_parameters, ParameterRemove

@deprecated_parameters(
    ParameterRemove(old_name="verbose", version="1.5.0", when="v2.0.0"),
)
def compute(data):
    """Compute things."""
    return data
```

autodoc then renders:

```text
compute(data)

   Compute things.

   Deprecated since version 1.5.0: Argument "verbose" for "compute" is
   deprecated since 1.5.0, its value is ignored and it will no longer be
   accepted in v2.0.0
```

The directive argument is the `version` of the deprecation, or its `when` when no version is given.

## Example

[example/](example) is a small library that uses every kind of deprecation once, with the calls that
an unmigrated caller would make. One command each shows the three ways in which they are reported:

```bash
cd example
python mylibrary.py                        # the runtime warnings
mypy --config-file mypy.ini mylibrary.py   # the same, before anything runs
sphinx-build -b html docs build            # the deprecations in the documentation
```

See [example/README.md](example/README.md) for what each of them prints.

## Limitations

- Only mypy reports deprecated parameters directly. Other type checkers have no
  plugin system, and need the generated overloads described above.
- A deprecated value is only detected statically when it is given as a literal,
  and only widened in the signature for types that have a `Literal`, so not for
  floats. At runtime any value is compared.
- Calls through an alias, `functools.partial` or `**kwargs` unpacking are not
  detected by mypy.
- A parameter that is removed or becomes keyword-only can only be rescued from
  the position it had if it was among the last positional ones. Otherwise an
  argument given for it is indistinguishable from one given for the parameter
  that now occupies that position, and the decorator refuses the `old_index`.
- The decorator cannot be applied to a class. Apply it to `__init__` instead,
  which is reported by mypy on calls to the class.
- Decorated coroutine functions are recognized by `inspect.iscoroutinefunction`
  only from python 3.12. In earlier versions only `asyncio.iscoroutinefunction`
  recognizes them.

## Contributing

Contributions are welcome, please open an issue or pull request in
[GitHub](https://github.com/mauvilsa/deprecated-parameters).

### Development environment

```bash
git clone https://github.com/mauvilsa/deprecated-parameters.git
cd deprecated-parameters
python -m venv venv
source venv/bin/activate
pip install -e ".[test,dev]"
pre-commit install
```

Run the tests with:

```bash
pytest
```

Note that mypy is unable to resolve [PEP
660](https://peps.python.org/pep-0660/) editable installs, which is what `pip
install -e` creates. The tests work around this by passing the location of the
package to mypy as `mypy_path`, so they can be run from any working directory.
If you invoke mypy yourself on code that imports `deprecated_parameters` from an
editable install, you may need to do the same.

To run the tests against all supported python versions:

```bash
tox
```

## License

MIT, see [LICENSE](LICENSE).
