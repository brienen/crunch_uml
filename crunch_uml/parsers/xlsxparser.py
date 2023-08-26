import logging

from crunch_uml import db
from crunch_uml.parsers.parser import Parser, ParserRegistry

logger = logging.getLogger()


#@ParserRegistry.register("xlsx")
class XLSXParser(Parser):
    def parse(self, args, database: db.Database):
        pass
