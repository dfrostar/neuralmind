import os
import importlib

importlib.import_module(os.environ["PLUGIN"])
