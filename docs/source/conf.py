import sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(root / "src" / "lib"))
sys.path.insert(0, str(root / "src" / "tools"))

project = "buvis-gems"
copyright = "2024, Tomáš Bouška"
author = "Tomáš Bouška"

extensions = ["sphinx.ext.autodoc", "sphinx.ext.napoleon", "sphinx.ext.githubpages"]
autodoc_mock_imports = ["buvis.pybase.zettel._core"]

templates_path = ["_templates"]
exclude_patterns = []

html_theme = "sphinx_rtd_theme"
html_static_path = ["_static"]
