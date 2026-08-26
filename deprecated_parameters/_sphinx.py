"""Documentation of the deprecations as sphinx ``.. deprecated::`` directives.

The directives are appended to the docstring of the decorated callable, one per version, so that the
deprecations show up in the documentation. This only happens while sphinx is building, since outside of
a build the extra text would be a cost with no benefit, so nothing needs to be enabled for it to work.
"""

import sys
import textwrap
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:  # pragma: no cover
    from ._decorator import DeprecatedParameters

__all__ = [
    "deprecation_directives",
]

#: Modules that only get imported when sphinx is actually building, unlike ``sphinx`` itself which any
#: application could import for unrelated reasons.
sphinx_build_modules = ("sphinx.application", "sphinx.ext.autodoc")


def documenting() -> bool:
    """Whether a sphinx build is in progress, and the deprecations should be documented."""
    return any(module in sys.modules for module in sphinx_build_modules)


def deprecation_directives(func_name: str, deprecations: "DeprecatedParameters") -> str:
    """Render the deprecations as sphinx ``.. deprecated::`` directives, one per deprecation.

    The directive holds a single message on purpose. Sphinx merges the first paragraph of its content
    into the "Deprecated since version X:" line, so grouping several messages in one directive renders
    badly, whereas repeating the directive is correct in every builder.
    """
    blocks = []
    for deprecation in deprecations.all:
        version = deprecation.version or deprecation.when
        # No wrapping, sphinx reflows the text. Indenting is all that the directive body needs.
        message = textwrap.indent(deprecation.format(func_name), "   ")
        blocks.append(f".. deprecated:: {version}\n{message}")
    return "\n\n".join(blocks)


def _indent_of(docstring: str) -> str:
    """Indentation used by the body of a docstring, to append to it consistently."""
    lines = [line for line in docstring.splitlines()[1:] if line.strip()]
    if not lines:
        return ""
    return min(line[: len(line) - len(line.lstrip())] for line in lines)


def document_deprecations(
    docstring: Optional[str],
    func_name: str,
    deprecations: "DeprecatedParameters",
) -> str:
    """Docstring with the deprecation directives appended, indented like its body."""
    directives = deprecation_directives(func_name, deprecations)
    if not docstring:
        return directives
    body = textwrap.indent(directives, _indent_of(docstring))
    return f"{docstring.rstrip()}\n\n{body}\n"
