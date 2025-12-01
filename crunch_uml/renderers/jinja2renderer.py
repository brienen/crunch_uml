import html
import json
import logging
import os
import re
import warnings

import inflection
import validators
from bs4 import BeautifulSoup, MarkupResemblesLocatorWarning
from jinja2 import Environment, FileSystemLoader
from markdownify import markdownify as md

import crunch_uml.schema as sch
from crunch_uml import const, db, util
from crunch_uml.exceptions import CrunchException
from crunch_uml.renderers.renderer import ClassRenderer, ModelRenderer, RendererRegistry

logger = logging.getLogger()


def fix_mojibake(text: str) -> str:
    try:
        # Tekst die ten onrechte als Windows-1252 is gelezen, maar eigenlijk UTF-8 was
        return text.encode('latin1').decode('utf-8')
    except Exception:
        return text  # Als het niet fout is, laat het zoals het is


# Herbruikbare regex om "meerregeligheid" te detecteren
_MULTILINE_RE = re.compile(
    r'(<\s*br\s*/?\s*>|</\s*p\s*>|<\s*li\b|<\s*p\b|\n)',
    flags=re.IGNORECASE,
)


def _html_to_markdown_lines(raw: str) -> list[str]:
    """
    Helper:
    - HTML entities decoderen
    - HTML → Markdown (incl. lijsten) via markdownify
    - trailing spaces weg
    - max 1 lege regel achter elkaar
    - geeft een lijst met regels terug
    """
    markdown = md(
        html.unescape(raw),
        heading_style="ATX",  # # H1, ## H2, ...
        bullets="*",  # <ul><li> → * item
        strip=["style", "script"],
    )

    lines = [ln.rstrip() for ln in markdown.splitlines()]
    cleaned_lines = []
    previous_blank = False

    for ln in lines:
        if ln.strip() == "":
            if not previous_blank:  # max 1 lege regel
                cleaned_lines.append("")
            previous_blank = True
        else:
            cleaned_lines.append(ln)
            previous_blank = False

    # trailing en leading lege regels eraf
    while cleaned_lines and cleaned_lines[0].strip() == "":
        cleaned_lines.pop(0)
    while cleaned_lines and cleaned_lines[-1].strip() == "":
        cleaned_lines.pop()

    return cleaned_lines


def fix_and_format_text(text: str, mode: str = "markdown", depth: int = 1) -> str:
    """
    Formatteert en escapt tekst afhankelijk van het doel:

    - mode="markdown":
        * Enkelregelig:
            - HTML-tags strippen
            - HTML-entities decoderen
            - platte tekst teruggeven
        * Meerregelig:
            - HTML → Markdown (incl. lijsten)
            - regels opschonen
            - elke regel in een blockquote (> ...)
    - mode="alert":
        * HTML → Markdown (incl. lijsten)
        * bullets normaliseren naar "- "
        * tekst geschikt maken voor gebruik in een JS alert-string:
            - newlines → \n
            - backslash → \\\\
            - " → \\\"

    Parameters
    ----------
    text : str
        De bron-HTML of -tekst.
    mode : {"markdown", "alert"}
        Doelcontext van de tekst.

    Returns
    -------
    str
        Geformatteerde tekst.
    """

    if not text:
        return ""

    text = fix_mojibake(text)
    raw = text.strip()

    # Bepaal of er feitelijk meerdere regels / blokken in zitten
    has_multiline = bool(_MULTILINE_RE.search(raw))

    # ---------------------------
    #  mode = "markdown"
    # ---------------------------
    if mode == "markdown":
        if not has_multiline:
            # Enkelregelig: HTML strippen + entities decoderen → platte tekst
            warnings.filterwarnings("ignore", category=MarkupResemblesLocatorWarning)
            soup = BeautifulSoup(raw, "html.parser")
            plain = soup.get_text(separator=" ", strip=True)
            return plain if isinstance(plain, str) else html.unescape(plain)

        # Meerregelig: HTML → Markdown → blockquote
        lines = _html_to_markdown_lines(raw)

        if not lines:
            return ""

        chr = ">" * depth + " "
        quoted_lines = [(chr + ln) if ln.strip() != "" else chr.rstrip() for ln in lines]
        return "\n" + "\n".join(quoted_lines)

    # ---------------------------
    #  mode = "alert"
    # ---------------------------
    elif mode == "alert":
        # Voor alerts altijd via dezelfde pipeline:
        # HTML → Markdown-lijnen
        lines = _html_to_markdown_lines(raw)

        # Bullets normaliseren: "* item", "- item", "+ item" → "- item"
        norm_lines = []
        bullet_re = re.compile(r"^(\s*)([-*+])\s+(.*)")

        for ln in lines:
            m = bullet_re.match(ln)
            if m:
                indent, _, rest = m.groups()
                ln = f"{indent}- {rest}"
            norm_lines.append(ln)

        base = "\n".join(norm_lines)

        if not base:
            return ""

        # Escapen voor gebruik in een JS alert("...") string
        js = base.replace("\\", "\\\\")  # backslashes escapen
        js = js.replace('"', '\\"')  # dubbele quotes escapen
        js = js.replace("\n", "\\n")  # echte newline → \n literal

        return js

    else:
        raise ValueError("Unsupported mode. Use 'markdown' or 'alert'.")


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

        # Zet tekst om naar snake_case
        env.filters["snake_case"] = lambda s: (inflection.underscore(s.replace(" ", "")) if isinstance(s, str) else "")

        # Zet tekst om naar PascalCase
        env.filters["pascal_case"] = lambda s: (inflection.camelize(s.replace(" ", "")) if isinstance(s, str) else "")

        # Zet tekst om naar camelCase
        env.filters["camel_case"] = lambda s: (
            inflection.camelize(s.replace(" ", ""), False) if isinstance(s, str) else ""
        )

        # Vervang spaties en koppeltekens door underscores (Python-compatibel)
        env.filters["pythonize"] = lambda s: (s.replace(" ", "").replace("-", "_") if isinstance(s, str) else "")

        # Voeg Markdown quote-tekens toe aan nieuwe regels
        env.filters["md_newline"] = lambda s: (
            s.replace("\n", "\n> ").replace("\r\n", "\r\n> ") if isinstance(s, str) else ""
        )

        # Verwijder nieuwe regels uit de tekst
        env.filters["del_newline"] = lambda s: (s.replace("\n", " ").replace("\r\n", " ") if isinstance(s, str) else "")

        # Maak van een URL een klikbare Markdown-link
        env.filters["set_url"] = lambda s: f"[{s}]({s})" if validators.url(s) else s

        # Verwijder items uit een lijst waarvoor een bepaalde methode True retourneert
        env.filters["reject_method"] = lambda iterable, method_name: [
            item for item in iterable if not getattr(item, method_name)()
        ]

        # Sorteer relaties op 'order', waarbij None als oneindig groot wordt behandeld
        env.filters["sort_order"] = lambda rels: sorted(
            rels if rels else [], key=lambda rel: float('inf') if rel.order is None else rel.order
        )

        # Verander meerdere regels tekst in Markdown met <br> scheiding
        env.filters["mdonize"] = lambda s: (
            "<br>".join(line.strip() for line in s.strip().splitlines()) if isinstance(s, str) else ""
        )

        # Formatteer en escape tekst voor gebruik in alert boxes
        env.filters["fix_and_format_alert"] = lambda s: fix_and_format_text(s, mode="alert")

        # Formatteer en escape tekst voor gebruik in markdown
        env.filters["fix_and_format"] = lambda s, depth=1: fix_and_format_text(s, mode="markdown", depth=depth)

        # Verwijder voor- en achterliggende spaties
        env.filters["trim"] = lambda s: (s.strip() if isinstance(s, str) else "")

        # Verwijder alle HTML-tags uit de tekst
        env.filters["strip_html"] = lambda s: re.sub(r"<[^>]*>", "", s) if isinstance(s, str) else s

        # Zet tekst om naar Title Case
        env.filters["title_case"] = lambda s: inflection.titleize(s) if isinstance(s, str) else ""

        # Maak een slug (URL-vriendelijke tekst)
        env.filters["slugify"] = lambda s: inflection.parameterize(s, separator="-") if isinstance(s, str) else ""

        # Zet enkelvoud naar meervoud
        env.filters["pluralize"] = lambda s: inflection.pluralize(s) if isinstance(s, str) else ""

        # Zet meervoud naar enkelvoud
        env.filters["singularize"] = lambda s: inflection.singularize(s) if isinstance(s, str) else ""

        # Kort tekst af tot een bepaalde lengte
        env.filters["truncate"] = lambda s, length=80: (
            (s[:length] + "...") if isinstance(s, str) and len(s) > length else s
        )

        # Voeg Markdown blockquote syntax toe aan iedere regel
        env.filters["blockquote"] = lambda s: (
            "\n".join(["> " + line for line in s.splitlines()]) if isinstance(s, str) else s
        )

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


@RendererRegistry.register(
    "plain_html",
    descr="Renderer that generates simple HTML documentation for the model.",
)
class PlainHTMLRenderer(Jinja2Renderer):
    """
    Renderer that produces basic HTML documentation for each model package.
    This renderer outputs one HTML file per package using a simple Jinja2 template.
    """

    template = "plain_html.j2"  # type: ignore
    enforce_output_package_ids = False

    def render(self, args, schema: sch.Schema):
        """
        Render the model packages into simple HTML files.
        """
        filename, extension = os.path.splitext(args.outputfile)
        template, templatedir = self.getTemplateAndDir(args)

        file_loader = FileSystemLoader(templatedir)
        env = Environment(loader=file_loader)
        self.addFilters(env)

        models = self.getModels(args, schema)
        if not models:
            msg = "No packages found to render for PlainHTMLRenderer"
            logger.error(msg)
            raise CrunchException(msg)

        for index, package in enumerate(models):
            template_obj = env.get_template(template)
            output = template_obj.render(package=package, args=args)

            outputfilename = (
                self.getFilename(filename, ".html", package) if package.name is not None else f"{filename}_{index}.html"
            )
            with open(outputfilename, "w") as file:
                file.write(output)
            logger.info(f"Plain HTML documentation generated: {outputfilename}")


@RendererRegistry.register(
    "model_overview_md",
    descr="Renderer that generates a single markdown file with an overview of all models.",
)
class ModelOverviewMarkdownRenderer(Jinja2Renderer):
    """
    Renderer that creates one markdown file summarizing all models in the schema.
    Useful for generating a high-level overview in markdown format.
    """

    template = "model_overview_markdown.j2"  # type: ignore
    enforce_output_package_ids = False

    def render(self, args, schema: sch.Schema):
        """
        Render a single markdown file containing an overview of all models.
        """
        filename, extension = os.path.splitext(args.outputfile)
        template, templatedir = self.getTemplateAndDir(args)

        file_loader = FileSystemLoader(templatedir)
        env = Environment(loader=file_loader)
        self.addFilters(env)

        models = self.getModels(args, schema)
        if not models:
            msg = "No packages found to render for ModelOverviewMarkdownRenderer"
            logger.error(msg)
            raise CrunchException(msg)

        template_obj = env.get_template(template)
        output = template_obj.render(models=models, args=args)

        outputfilename = f"{filename}.md"
        with open(outputfilename, "w") as file:
            file.write(output)
        logger.info(f"Model overview markdown generated: {outputfilename}")


@RendererRegistry.register(
    "er_diagram",
    descr="Renderer that generates an ER diagram visualization via Graphviz.",
)
class ERDiagramRenderer(Jinja2Renderer):
    """
    Renderer that produces a visual Entity-Relationship diagram for the model.
    Uses Graphviz to create graphical representations of classes and associations.
    """

    template = "er_diagram.dot.j2"  # type: ignore
    enforce_output_package_ids = False

    def render(self, args, schema: sch.Schema):
        """
        Render ER diagrams in DOT format for each model package.
        The output can then be processed with Graphviz tools to produce images.
        """
        filename, extension = os.path.splitext(args.outputfile)
        template, templatedir = self.getTemplateAndDir(args)

        file_loader = FileSystemLoader(templatedir)
        env = Environment(loader=file_loader)
        self.addFilters(env)

        models = self.getModels(args, schema)
        if not models:
            msg = "No packages found to render for ERDiagramRenderer"
            logger.error(msg)
            raise CrunchException(msg)

        for index, package in enumerate(models):
            template_obj = env.get_template(template)
            output = template_obj.render(package=package, args=args)

            outputfilename = (
                self.getFilename(filename, ".dot", package) if package.name is not None else f"{filename}_{index}.dot"
            )
            with open(outputfilename, "w") as file:
                file.write(output)
            logger.info(f"ER diagram DOT file generated: {outputfilename}")


@RendererRegistry.register(
    "openapi",
    descr="Renderer that generates OpenAPI YAML specification for the model.",
)
class OpenAPIRenderer(Jinja2Renderer):
    """
    Renderer that creates an OpenAPI YAML specification from the model schema.
    This is useful for generating REST API documentation automatically.
    """

    template = "openapi.yaml.j2"  # type: ignore
    enforce_output_package_ids = True

    def render(self, args, schema: sch.Schema):
        """
        Render the OpenAPI YAML file for the model schema.
        """
        filename, extension = os.path.splitext(args.outputfile)
        template, templatedir = self.getTemplateAndDir(args)

        file_loader = FileSystemLoader(templatedir)
        env = Environment(loader=file_loader)
        self.addFilters(env)

        models = self.getModels(args, schema)
        if not models:
            msg = "No packages found to render for OpenAPIRenderer"
            logger.error(msg)
            raise CrunchException(msg)

        # OpenAPI typically outputs a single file, so render all models together
        template_obj = env.get_template(template)
        output = template_obj.render(models=models, args=args)

        outputfilename = f"{filename}.yaml"
        with open(outputfilename, "w") as file:
            file.write(output)
        logger.info(f"OpenAPI YAML specification generated: {outputfilename}")
