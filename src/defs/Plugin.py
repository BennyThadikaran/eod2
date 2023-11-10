from importlib import import_module
from argparse import ArgumentParser


class Plugin:

    def __init__(self):
        self.plugins = []

    def register(self, plugins: dict, parser: ArgumentParser):
        for plugin in plugins.values():
            instance = import_module(f'plugin.{plugin["name"]}')
            instance.load(parser)
            self.plugins.append(instance)

    def run(self, *args):
        for plugin in self.plugins:
            plugin.main(*args)
