import logging

from crunch_uml.transformers.plugin import Plugin

logger = logging.getLogger()


class TestPlugin(Plugin):
    def transformLogic(self, args, root_package, schema_from, schema_to):
        logger.info("Passing transformLogic in TestPlugin.")
