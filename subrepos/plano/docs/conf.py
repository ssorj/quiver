# import os
# import sys

# sys.path.insert(0, os.path.abspath("../python"))

extensions = [
    "sphinx.ext.autodoc",
]

# autodoc_member_order = "bysource"
# autodoc_default_flags = ["members", "undoc-members", "inherited-members"]

autodoc_default_options = {
    "members": True,
    "member-order": "bysource",
    "undoc-members": True,
    "imported-members": True,
    "exclude-members": "PlanoProcess",
}

master_doc = "index"
project = u"Plano"
copyright = u"1975"
author = u"Justin Ross"

version = u"0.1.0"
release = u""

pygments_style = "sphinx"
html_theme = "nature"

html_theme_options = {
    "nosidebar": True,
}
