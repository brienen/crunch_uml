from abc import ABC


class Plugin(ABC):
    def transformLogic(self, args, root_package, schema_from, schema_to):
        pass
