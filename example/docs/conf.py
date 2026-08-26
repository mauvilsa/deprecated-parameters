"""Sphinx configuration of the example, the only thing needed is autodoc.

Nothing has to be enabled for the deprecations to be documented. The decorator appends a
``.. deprecated::`` directive to the docstring while sphinx is building, and only then.
"""

import os
import sys

#: The directory of mylibrary, which is the parent of this one, so that autodoc can import it.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

project = "mylibrary"
author = "deprecated-parameters"

extensions = ["sphinx.ext.autodoc"]

#: So that the docstring of __init__, which is where the decorator is applied, is shown for the class.
autoclass_content = "both"
autodoc_member_order = "bysource"

html_theme = "alabaster"
