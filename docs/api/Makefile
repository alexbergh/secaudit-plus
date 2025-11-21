# Minimal makefile for Sphinx documentation

# You can set these variables from the command line
SPHINXOPTS    ?=
SPHINXBUILD   ?= sphinx-build
SOURCEDIR     = .
BUILDDIR      = _build

# Put it first so that "make" without argument is like "make help"
help:
	@$(SPHINXBUILD) -M help "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)

.PHONY: help Makefile clean apidoc

# Generate API documentation from source
apidoc:
	sphinx-apidoc -f -o modules ../../modules
	sphinx-apidoc -f -o modules/secaudit ../../secaudit
	sphinx-apidoc -f -o modules/seclib ../../seclib
	sphinx-apidoc -f -o modules/utils ../../utils

# Clean generated files
clean:
	rm -rf $(BUILDDIR)
	rm -rf modules

# Catch-all target: route all unknown targets to Sphinx
%: Makefile
	@$(SPHINXBUILD) -M $@ "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)
