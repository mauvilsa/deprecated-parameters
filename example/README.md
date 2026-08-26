# Example

[mylibrary.py](mylibrary.py) is a small library in which every kind of parameter deprecation is used
once, plus the calls that a caller which has not migrated yet would make. The three ways in which
those calls are reported can each be seen by running one command.

Install what is needed for all three:

```bash
pip install "deprecated-parameters[mypy]" sphinx
```

## Runtime warnings

```bash
python mylibrary.py
```

Each deprecated call warns, pointing at the line that made it:

```text
--- ParameterRename
mylibrary.py:164: DeprecationWarning: Argument "n_jobs" for "compute" is deprecated since 1.5.0, it
has been renamed to "workers" and "n_jobs" will no longer be accepted in v2.0.0
  compute([1, 2, 3], n_jobs=4)
```

## The same, reported by mypy

```bash
mypy --config-file mypy.ini mylibrary.py
```

The only thing [mypy.ini](mypy.ini) does is enable the plugin. Every call that warns at runtime is an
error under the `deprecated-arg` error code, with the same message, before anything runs:

```text
mylibrary.py:164: error: Argument "n_jobs" for "compute" is deprecated since 1.5.0, it has been
renamed to "workers" and "n_jobs" will no longer be accepted in v2.0.0  [deprecated-arg]
```

The seven errors are the point of the example, so a non-zero exit code here is the expected result.

If mypy instead reports that `deprecated_parameters` cannot be found, the package is installed as
an editable install, which mypy cannot resolve. Give it the location of the package:

```bash
MYPYPATH=.. mypy --config-file mypy.ini mylibrary.py
```

## The deprecations in the documentation

```bash
sphinx-build -b html docs build
```

Open `build/index.html`. Each documented callable has a *Deprecated since version* note per
deprecation, holding the same message again. Nothing enables this: while sphinx is building, and only
then, the decorator appends a `.. deprecated::` directive to the docstring, so [docs/conf.py](docs/conf.py)
is a plain autodoc configuration.

## What is in the module

| Callable | Deprecation | What it shows |
| --- | --- | --- |
| `read_table` | `ParameterRemove` | A parameter taken out of the signature, with `old_index` so that it is also recognized when given positionally |
| `compute` | `ParameterRename` | A renamed parameter, whose value is forwarded to the new name |
| `train` | `ParameterPositional` | A parameter that became keyword-only, whose positional value is moved to its keyword |
| `solve` | `ParameterValueRemove` | A single deprecated value of a parameter, replaced with its successor |
| `configure` | `ParameterRemove` with `transform=None` | Warning without changing the call, with a custom `message` and `FutureWarning` as the `category` |
| `Session` | `ParameterRename` in `__init__` | A constructor, which mypy reports on calls to the class |
