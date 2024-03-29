# -- General configuration -----------------------------------------------

extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.doctest',
    'sphinx.ext.intersphinx',
]

release = "0.19.2"

# Add any paths that contain templates here, relative to this directory.
templates_path = ['_templates']

# The suffix of source filenames.
source_suffix = '.rst'

# The master toctree document.
master_doc = 'index'

# General information about the project.
project = 'pyramid_zipkin'
copyright = '2018, Yelp, Inc'

exclude_patterns = []

pygments_style = 'sphinx'


# -- Options for HTML output ---------------------------------------------

html_theme = 'sphinxdoc'

html_static_path = ['_static']

htmlhelp_basename = 'zipkin-pydoc'


intersphinx_mapping = {
    'http://docs.python.org/': None
}
