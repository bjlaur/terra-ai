"""TerraAI - SOPEL IRC AI assistant plugin."""

__version__ = "0.0.1"

# Sopel loads the folder plugin by importing terra_ai/__init__.py.
# Everything Sopel needs to register must be visible from this module.
from .plugin import *  # noqa: F401,F403
