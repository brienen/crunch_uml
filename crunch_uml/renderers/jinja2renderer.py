import html
import json
import logging
import os
import re

import inflection
import validators
from charset_normalizer import from_bytes
from jinja2 import Environment, FileSystemLoader

import crunch_uml.schema as sch
from crunch_uml import const, db, util
from crunch_uml.exceptions import CrunchException
from crunch_uml.renderers.renderer import ClassRenderer, ModelRenderer, RendererRegistry

logger = logging.getLogger()


@RendererRegistry.register(
    "jinja2",
    descr="Renderer that uses Jinja2 to renders one file per model in the database, "
    + "where a model is a package that includes at least one Class. "
    + ' Needs parameter "output_jinja2_template" and "output_jinja2_templatedir".',
)
class Jinja2Renderer(ModelRenderer):
    """
    Renders all model packages using jinja2 and a template.
    A model package is a package with at least 1 class inside
    """

    templatedir = None
    template = None
    enforce_output_package_ids = False

    def getTemplateAndDir(self, args):  # sourcery skip: raise-specific-error
        # get templatedir to be used
        if self.templatedir is not None:
            templatedir = self.templatedir
        elif args.output_jinja2_templatedir is not None:
            templatedir = args.output_jinja2_templatedir
        else:
            # Use the virtual environment's template directory if no templatedir is provided
            templatedir = util.find_module_path("crunch_uml")
            if templatedir:
                templatedir = os.path.join(templatedir, "templates")
            if not os.path.isdir(templatedir):
                templatedir = const.TEMPLATE_DIR

        if not os.path.isdir(templatedir):
            msg = f"Template directory with value {templatedir} does not exist, exiting"
            logger.error(msg)
            raise CrunchException(msg)
        logger.debug(f"Rendering with templatedir {templatedir}")

        # get template to be used
        if self.template is not None:
            template = self.template
        elif args.output_jinja2_template is not None:
            template = args.output_jinja2_template
        else:
            msg = "No template provided voor Jinja2, exiting"
            logger.error(msg)
            raise CrunchException(msg)
        logger.debug(f"Rendering with template {template}")
        return template, templatedir

    def addFilters(self, env):
        def fix_and_format(s):
            if isinstance(s, bytes):
                result = from_bytes(s).best()
                if result:
                    s = str(result)
                else:
                    return ""
            elif not isinstance(s, str):
                return ""

            s = html.unescape(s)

            def normalize_bullet(line):
                # Check op opsommingsteken na eventuele inspringing
                match = re.match(r"^(\s*)([-■•*·●◦‣›»▪–—])(\s+)(.*)", line)
                if match:
                    indent, _, spacing, rest = match.groups()
                    return f"{indent}•{spacing}{rest}"
                return line

            lines = s.strip().splitlines()
            lines = [normalize_bullet(line.rstrip()) for line in lines if line.strip() != ""]
            return "<br>".join(lines)

        # Voeg het inflection filter toe
        env.filters["snake_case"] = lambda s: (inflection.underscore(s.replace(" ", "")) if isinstance(s, str) else "")
        env.filters["pascal_case"] = lambda s: (inflection.camelize(s.replace(" ", "")) if isinstance(s, str) else "")
        env.filters["camel_case"] = lambda s: (
            inflection.camelize(s.replace(" ", ""), False) if isinstance(s, str) else ""
        )
        env.filters["pythonize"] = lambda s: (s.replace(" ", "").replace("-", "_") if isinstance(s, str) else "")
        env.filters["md_newline"] = lambda s: (
            s.replace("\n", "\n> ").replace("\r\n", "\r\n> ") if isinstance(s, str) else ""
        )
        env.filters["del_newline"] = lambda s: (s.replace("\n", " ").replace("\r\n", " ") if isinstance(s, str) else "")
        env.filters["set_url"] = lambda s: f"[{s}]({s})" if validators.url(s) else s
        env.filters["reject_method"] = lambda iterable, method_name: [
            item for item in iterable if not getattr(item, method_name)()
        ]
        env.filters["sort_order"] = lambda rels: sorted(
            rels if rels else [], key=lambda rel: float('inf') if rel.order is None else rel.order
        )
        env.filters["mdonize"] = lambda s: (
            "<br>".join(line.strip() for line in s.strip().splitlines()) if isinstance(s, str) else ""
        )
        env.filters["fix_and_format"] = fix_and_format

    def getFilename(self, inputfilename, extension, uml_generic):
        return f"{inputfilename}_{uml_generic.name}{extension}"

    def render(self, args, schema: sch.Schema):
        # setup output filename
        filename, extension = os.path.splitext(args.outputfile)

        # get template and templatedir
        template, templatedir = self.getTemplateAndDir(args)

        # sourcery skip: raise-specific-error
        # Settup environment for rendering using Jinja2
        file_loader = FileSystemLoader(templatedir)
        env = Environment(loader=file_loader)
        self.addFilters(env)

        # Check to see if a list of Package ids is provided
        # if self.enforce_output_package_ids and args.output_package_ids is None:
        #    msg = "Usage of parameter --output_package_ids is enforced for this renderer. Not provided, exiting."
        #    logger.error(msg)
        #    raise CrunchException(msg)

        # Get list of packages that are to be rendered
        models = self.getModels(args, schema)
        if len(models) is None:
            msg = "Cannot render output: packages do not exist"
            logger.error(msg)
            raise CrunchException(msg)

        # Render all packages that are named
        for index, package in enumerate(models):
            # Render output
            template = env.get_template(template)
            output = template.render(package=package, args=args)

            outputfilename = (
                self.getFilename(filename, extension, package)
                if package.name is not None
                else f"{filename}_{index}{extension}"
            )
            with open(outputfilename, "w") as file:
                file.write(output)


@RendererRegistry.register(
    "ggm_md",
    descr="Renderer renders one basic markdown file per model in the database, "
    + "where a model is a package that includes at least one Class. ",
)
class GGM_MDRenderer(Jinja2Renderer):
    template = "ggm_markdown.j2"  # type: ignore
    enforce_output_package_ids = True  # Enforce list of Package ids


def getJSONDatatype(
    self,  # "koppel_{{ associatie.name | snake_case }}_{{ associatie.id}}"
):
    if self.primitive is not None:
        if str(self.primitive).lower().startswith("bool"):
            return '"type": "boolean"'
        elif str(self.primitive).lower().startswith("int"):
            return '"type": "integer"'
        elif str(self.primitive).lower().startswith("bedrag"):
            return '"$ref": "#/$defs/bedrag"'  # Needs to be defined in Jinja2 template
        elif "mail" in str(self.primitive).lower():
            return '"$ref": "#/$defs/email"'  # Needs to be defined in Jinja2 template
        elif str(self.primitive).lower() in ["tijd", "time"]:
            return '"$ref": "#/$defs/tijd"'  # Needs to be defined in Jinja2 template
        elif str(self.primitive).lower() in ["datum", "date"]:
            return '"$ref": "#/$defs/datum"'  # Needs to be defined in Jinja2 template
        elif str(self.primitive).lower() in ["datumtijd", "datetime"]:
            return '"$ref": "#/$defs/datum-tijd"'  # Needs to be defined in Jinja2 template
        else:
            return '"type": "string"'
    elif self.enumeration is not None:
        return f'"$ref": "#/$defs/{self.enumeration.name}"'  # Needs to be defined in Jinja2 template
    elif self.type_class is not None:
        return f'"$ref": "#/$defs/{self.type_class.name}"'  # Needs to be defined in Jinja2 template
    else:
        return '"type": "string"'


def getVerplichteAttributen(self):
    set_verplicht = {attr.name for attr in self.attributes if attr.verplicht}
    set_verplichr_rel = {
        (
            assoc.src_role.lower()
            if assoc.src_role is not None and assoc.src_role != ""
            else assoc.dst_class.name.lower()
        )
        for assoc in self.uitgaande_associaties
        if assoc.isEnkelvoudig(dst=True) and assoc.isVerplicht(dst=True) and assoc.dst_class.name is not None
    }
    return list(set_verplicht.union(set_verplichr_rel))


@RendererRegistry.register(
    "json_schema",
    descr="Renderer renders a JSON schema from a single package. ",
)
class JSON_SchemaRenderer(Jinja2Renderer, ClassRenderer):
    template = "json_schema.j2"  # type: ignore
    enforce_output_package_ids = True  # Enforce list of Package ids

    def render(self, args, schema: sch.Schema):
        logger.info("Start rendering JSON schema met Jinja2")
        try:
            # Add methods for correct JSON datatype handling
            db.Attribute.getJSONDatatype = getJSONDatatype  # No error!
            db.Class.getVerplichteAttributen = getVerplichteAttributen  # No error!

            # Setup output filename
            filename, extension = os.path.splitext(args.outputfile)
            logger.debug(f"Output file split into filename: {filename} and extension: {extension}")

            # Obtain template and templatedir with error handling
            try:
                template, templatedir = self.getTemplateAndDir(args)
                logger.info(f"Obtained template: {template} and templatedir: {templatedir}")
            except Exception as e:
                logger.error(f"Fout bij ophalen template of template directory: {e}")
                raise

            # Setup Jinja2 environment
            try:
                file_loader = FileSystemLoader(templatedir)
                env = Environment(loader=file_loader)
                self.addFilters(env)
                logger.debug("Jinja2 environment setup complete")
            except Exception as e:
                logger.error(f"Fout bij opzetten van de Jinja2 omgeving: {e}")
                raise

            # Retrieve the class to render
            try:
                clazz = self.getClass(args, schema)
                if clazz is None:
                    raise CrunchException("Geen class gevonden om te renderen")
                logger.info(f"Class geladen: {clazz.name}")
            except Exception as e:
                logger.error(f"Fout bij ophalen van class: {e}")
                raise

            # Load template
            try:
                template_obj = env.get_template(template)
                logger.info(f"Template {template} succesvol geladen")
            except Exception as e:
                logger.error(f"Fout bij laden van Jinja2 template: {e}")
                raise

            # Render the template
            try:
                output = template_obj.render(clazz=clazz, args=args)
                logger.info("Template succesvol gerenderd")
            except Exception as e:
                logger.error(f"Fout bij renderen van template: {e}")
                raise

            # Format JSON output
            try:
                data = json.loads(output)
                formatted_json = json.dumps(data, indent=4)
                logger.info("JSON output succesvol geformatteerd")
            except Exception as ex:
                formatted_json = output
                logger.warning(f"Kon JSON niet formatteren: {ex}")

            # Determine output filename and write to file
            outputfilename = (
                self.getFilename(filename, extension, clazz) if clazz.name is not None else f"{filename}{extension}"
            )
            try:
                with open(outputfilename, "w") as file:
                    file.write(formatted_json)
                logger.info(f"JSON schema geschreven naar: {outputfilename}")
            except Exception as e:
                logger.error(f"Fout bij schrijven naar bestand: {e}")
                raise

        except Exception as overall_exception:
            logger.error(f"Rendering mislukt: {overall_exception}")
            raise
        finally:
            if hasattr(db.Attribute, "getJSONDatatype"):
                del db.Attribute.getJSONDatatype
            if hasattr(db.Class, "getVerplichteAttributen"):
                del db.Class.getVerplichteAttributen
