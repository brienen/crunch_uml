DATABASE_URL = "sqlite:///crunch_uml.db"
NS_XMI = 'http://www.omg.org/spec/XMI/20110701'
NS_UML = 'http://www.omg.org/spec/UML/20110701'

TEMPLATE_DIR = './crunch_uml/templates'

CMD_IMPORT = 'import'
CMD_EXPORT = 'export'
CMD_TRANSFORM = 'transform'
# CMD_CHECK = 'check'
# CMD_FIX = 'fix'

DEFAULT_LOD_NS = 'http://example.org/myns/'
DEFAULT_SCHEMA = 'default'

ORPHAN_CLASS = '<Orphan Class>'

DESCRIPTION = "Crunch_uml reads UML Class model from multiple formats (including XMI, Enterprise Architect XMI, Excel, Json, and others), can perform transformations and renders them to other formats (including Markdown, json, json schema and many others)."
