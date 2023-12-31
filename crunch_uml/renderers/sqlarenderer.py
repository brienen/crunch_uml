import logging
import re
import inflection

from crunch_uml import const, db
from crunch_uml.excpetions import CrunchException
from crunch_uml.renderers.renderer import RendererRegistry
from crunch_uml.renderers.jinja2renderer import Jinja2Renderer

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


def getMeervoud(naamwoord):
    # Woorden die eindigen op een onbeklemtoonde 'e' krijgen 'n'
    if not isinstance(naamwoord, str):
        return ''
    # Woorden die eindigen op een onbeklemtoonde 'e' krijgen 'n'
    elif naamwoord.endswith('ie'):
        return f"{naamwoord}s"
    # Woorden die eindigen op een onbeklemtoonde 'e' krijgen 'n'
    elif naamwoord.endswith('e'):
        return f"{naamwoord}n"
    # Woorden die eindigen op een klinker (behalve 'e') krijgen 's'
    elif naamwoord[-1] in 'aiou':
        return f"{naamwoord}s"
    # Woorden die eindigen op 's', 'f' of 'ch' krijgen 'en'
    elif naamwoord.endswith(('s', 'f', 'ch')):
        return f"{naamwoord}en"
    # Default regel
    else:
        return f"{naamwoord}en"


def getPackageLst(self, package: db.Package):
    if package.parent_package is None or getPackageLst(self, package.parent_package) == '':
        return package.modelnaam_kort if package.modelnaam_kort is not None else ''
    else:
        return (f"{getPackageLst(self, package.parent_package)}_{package.modelnaam_kort}" 
                if package.modelnaam_kort is not None 
                else getPackageLst(self, package.parent_package))



@RendererRegistry.register(
    "sqla",
    descr='Renderer that renders SQLAlchemy 2.0 files. It uses Jinja2 and renders one file per model filled with classes of that model, '
    + 'where a model is a package that includes at least one Class. '
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
        env.filters['meervoud'] = getMeervoud
        env.filters['snake_case'] = lambda s: pythonize(inflection.underscore(s.replace(" ", ""))) if isinstance(s, str) else ''
        env.filters['pascal_case'] = lambda s: pythonize(inflection.camelize(s.replace(" ", ""))) if isinstance(s, str) else ''
        env.filters['camel_case'] = lambda s: pythonize(inflection.camelize(s.replace(" ", "")), False) if isinstance(s, str) else ''
        env.filters['pythonize'] = lambda s: pythonize(s.replace(" ", "").replace("-", "_")) if isinstance(s, str) else ''



    def render(self, args, database: db.Database):
        # place to set up custom code
        db.Package.getPackageLst = getPackageLst
        super().render(args, database)
        del db.Package.getPackageLst