DATABASE_URL = "sqlite:///crunch_uml.db"
NS_XMI = "http://www.omg.org/spec/XMI/20110701"
NS_UML = "http://www.omg.org/spec/UML/20110701"

TEMPLATE_DIR = "./crunch_uml/templates"

CMD_IMPORT = "import"
CMD_EXPORT = "export"
CMD_TRANSFORM = "transform"
# CMD_CHECK = 'check'
# CMD_FIX = 'fix'

DEFAULT_LOD_NS = "http://example.org/myns/"
DEFAULT_SCHEMA = "default"

ORPHAN_CLASS = "<Orphan Class>"
VERSION_STEP_MINOR = "minor"
VERSION_STEP_MAJOR = "major"
VERSION_STEP_NONE = "none"
DEFAULT_DATE_TIME_FORMAT = "%Y-%m-%d %H:%M:%S"

DESCRIPTION = "Crunch_uml reads UML Class model from multiple formats (including XMI, Enterprise Architect XMI, Excel, Json, and others), can perform transformations and renders them to other formats (including Markdown, json, json schema and many others)."

EA_REPO_MAPPER = {
    "id": "ea_guid",
    "name": "Name",
    "definitie": "Note",
    "alias": "Alias",
    "author": "Author",
    "version": "Version",
    "stereotype": "Stereotype",
    "created": "CreatedDate",
    "modified": "ModifiedDate",
}


EA_REPO_MAPPER_ATTRIBUTES = EA_REPO_MAPPER.copy()
EA_REPO_MAPPER_ATTRIBUTES["definitie"] = "Notes"
EA_REPO_MAPPER_ATTRIBUTES["primitive"] = "Type"

EA_REPO_MAPPER_LITERALS = EA_REPO_MAPPER_ATTRIBUTES.copy()
EA_REPO_MAPPER_LITERALS["type"] = "Type"

EA_REPO_MAPPER_ASSOCIATION = EA_REPO_MAPPER.copy()
EA_REPO_MAPPER_ASSOCIATION["definitie"] = "Notes"

TAG_STRATEGY_UPDATE = "update"
TAG_STRATEGY_UPSERT = "upsert"
TAG_STRATEGY_REPLACE = "replace"

RECORD_TYPE_RECORD = "record"
RECORD_TYPE_INDEXED = "indexed"

DEFAULT_LANGUAGE = "nl"
LANGUAGE_TRANSLATE_FIELDS = [
    "name",
    "definitie",
    "toelichting",
    "alias",
    "type",
    "synoniemen",
    "src_documentation",
    "dst_documentation",
]
