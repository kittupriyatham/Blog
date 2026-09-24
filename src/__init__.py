"""Application package.

Exists so `from src import syndication` resolves as a regular package for type
checkers and linters. Python 3 would import it anyway via implicit namespace
packages, but tooling reports it as unresolved without this file.
"""
