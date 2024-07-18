# mypy: ignore-errors
import logging
import re

import inflection

import crunch_uml.schema as sch
from crunch_uml import db, util
from crunch_uml.renderers.jinja2renderer import Jinja2Renderer
from crunch_uml.renderers.renderer import RendererRegistry

logger = logging.getLogger()


def pythonize(input_string):
    """
    Converts a given string to a valid Python variable name.
    """
    # Remove invalid characters
    # We use a regular expression to replace any non-word character (anything other than letters, digits, and underscores)
    # and also ensure the string does not start with a digit, as Python variable names cannot start with digits.
    return re.sub(r'\W|^(?=\d)', '_', input_string)


def getSQLADatatype(datatype):
    if isinstance(datatype, str):
        datatype = datatype.lower()

        if match := re.match(r'an(\d*)', datatype):
            return "String" if match[1] == '' else f"String({match[1]})"
        elif 'int' in datatype:
            return "Integer"
        elif 'date' in datatype:
            return "Date"
        elif 'boolean' in datatype:
            return "Boolean"
        elif 'text' in datatype:
            return "Text"
        else:
            return "String"
    elif isinstance(datatype, db.Enumeratie):
        return f"SAEnum({pythonize(inflection.camelize(datatype.name.replace(' ', '')))})"
    else:
        return "String"


def getPackageLst(self, package: db.Package):
    if package.parent_package is None or getPackageLst(self, package.parent_package) == '':
        return package.modelnaam_kort if package.modelnaam_kort is not None else ''
    else:
        return (
            f"{getPackageLst(self, package.parent_package)}_{package.modelnaam_kort}"
            if package.modelnaam_kort is not None
            else getPackageLst(self, package.parent_package)
        )


def getPackageImports(self: db.Package):
    imports = {}  # No error!
    for clazz in self.classes:
        for attr in clazz.attributes:
            if attr.type_class and attr.type_class.package and attr.type_class.package != self:
                if attr.type_class.package not in imports:
                    imports[attr.type_class.package] = set()
                imports[attr.type_class.package].add(attr.type_class)
            if attr.enumeration and attr.enumeration.package and attr.enumeration.package != self:
                if attr.enumeration.package not in imports:
                    imports[attr.enumeration.package] = set()
                imports[attr.enumeration.package].add(attr.enumeration)
        for associatie in clazz.uitgaande_associaties:
            if not associatie.hasOrphan() and associatie.dst_class.package and associatie.dst_class.package != self:
                if associatie.dst_class.package not in imports:
                    imports[associatie.dst_class.package] = set()
                imports[associatie.dst_class.package].add(associatie.dst_class)
        for associatie in clazz.inkomende_associaties:
            if not associatie.hasOrphan() and associatie.src_class.package and associatie.src_class.package != self:
                if associatie.src_class.package not in imports:
                    imports[associatie.src_class.package] = set()
                imports[associatie.src_class.package].add(associatie.src_class)
    return imports


# SQLA methods to be used while rendering templates
def nameSnakeCase(self):
    return pythonize(inflection.underscore(self.name.replace(" ", ""))) if isinstance(self.name, str) else ''


def namePascalCase(self):
    return pythonize(inflection.camelize(self.name.replace(" ", ""))) if isinstance(self.name, str) else ''


def tablename(self):  # "{{ package.getPackageLst(package) | lower }}__{{ class.name | snake_case }}"
    return f"{getPackageLst(self.package, self.package).lower()}__{nameSnakeCase(self)}"


def koppeltabelname(self):  # "koppel_{{ associatie.name | snake_case }}_{{ associatie.id}}"
    return f"{getPackageLst(self.src_class.package, self.src_class.package).lower()}__koppel_{self.getSQLAName()}_{self.id}"


def packagename(self: db.Package):
    return f"model_{namePascalCase(self)}"


def getFilename(inputfilename: str, extension: str, package: db.Package):
    # Verwijder de substring case-insensitief
    packagename = re.sub(re.escape('model'), "", package.name, flags=re.IGNORECASE)  # No error!
    packagename = pythonize(inflection.underscore(packagename.replace(" ", ""))) if isinstance(packagename, str) else ''
    return f"{inputfilename}_{packagename}{extension}"


@RendererRegistry.register(
    "sqla",
    descr=(
        'Renderer that renders SQLAlchemy 2.0 files. It uses Jinja2 and renders one file per model filled with classes'
        ' of that model, '
    )
    + 'where a model is a package that includes at least one Class. ',
)
class SQLARenderer(Jinja2Renderer):
    '''
    Renders all model packages using jinja2 and a template.
    A model package is a package with at least 1 class inside
    '''

    template = 'ggm_sqlalchemy.j2'  # type: ignore
    enforce_output_package_ids = True  # Enforce list of Package ids

    def addFilters(self, env):
        # Voeg het inflection filter toe
        super().addFilters(env)
        env.filters['sqla_datatype'] = getSQLADatatype
        env.filters['meervoud'] = util.getMeervoud
        env.filters['snake_case'] = lambda s: (
            pythonize(inflection.underscore(s.replace(" ", ""))) if isinstance(s, str) else ''
        )
        env.filters['pascal_case'] = lambda s: (
            pythonize(inflection.camelize(s.replace(" ", ""))) if isinstance(s, str) else ''
        )
        env.filters['camel_case'] = lambda s: (
            pythonize(inflection.camelize(s.replace(" ", "")), False) if isinstance(s, str) else ''
        )
        env.filters['pythonize'] = lambda s: (
            pythonize(s.replace(" ", "").replace("-", "_")) if isinstance(s, str) else ''
        )

    def getFilename(self, inputfilename, extension, package):
        return getFilename(inputfilename, extension, package)

    def getModels(self, args, schema):
        models = super().getModels(args, schema)
        return [model for model in models if model.modelnaam_kort is not None]

    def render(self, args, schema: sch.Schema):
        # place to set up custom code
        db.UML_Generic.getSQLAName = nameSnakeCase  # No error!
        db.Package.getPackageLst = getPackageLst
        db.Package.getPackageImports = getPackageImports
        db.Package.getSQLAName = lambda x: getFilename('model', '', x)
        db.Class.getSQLAName = namePascalCase
        db.Class.getSQLAAttrName = nameSnakeCase
        db.Class.getSQLATableName = tablename
        db.Enumeratie.getSQLAName = namePascalCase
        db.Enumeratie.getSQLAAttrName = nameSnakeCase
        db.EnumerationLiteral.getSQLAName = namePascalCase
        db.Association.getSQLAKoppelName = koppeltabelname

        super().render(args, schema)

        del db.UML_Generic.getSQLAName  # No error!
        del db.Package.getPackageLst
        del db.Package.getPackageImports
        del db.Package.getSQLAName
        del db.Class.getSQLAName
        del db.Class.getSQLAAttrName
        del db.Class.getSQLATableName
        del db.Enumeratie.getSQLAName
        del db.Enumeratie.getSQLAAttrName
        del db.EnumerationLiteral.getSQLAName
        del db.Association.getSQLAKoppelName
