import logging
import os

from jinja2 import Environment, FileSystemLoader

from crunch_uml import const, db
from crunch_uml.db import Class, Package
from crunch_uml.renderers.renderer import Renderer, RendererRegistry

logger = logging.getLogger()


@RendererRegistry.register(
    "jinja2",
    descr='Renderer that uses Jinja2 to renders one file per model in the database, '
    + 'where a model is a package that includes at least one Class. '
    + ' Needs parameter "output_jinja2_template" and "output_jinja2_templatedir".',
)
class Jinja2Renderer(Renderer):
    '''
    Renders all model packages using jinja2 and a template.
    A model package is a package with at least 1 class inside
    '''

    templatedir = None
    template = None
    enforce_output_package_ids = False

    def getPackages(self, args, database):
        lst = []
        if args.output_exclude_package_ids is not None:
            # Get package_ids to include
            excl_packageids = args.output_exclude_package_ids.split(',')
            excl_packageids = [elem.strip() for elem in excl_packageids]
        if args.output_package_ids is not None:
            # Get package_ids to include
            packageids = args.output_package_ids.split(',')
            packageids = [elem.strip() for elem in packageids]

            # subtract exclude list
            if args.output_exclude_package_ids:
                packageids = [pid for pid in packageids if pid not in excl_packageids]

        # Now find packages
        lst = []
        if args.output_package_ids is not None:
            # If list of p[ackage ids is supplied return query
            lst = database.get_session().query(Package).join(Class).filter(Package.id.in_(packageids)).distinct().all()
        elif args.output_exclude_package_ids is not None:
            # If only list of excluded model supplied return query
            lst = (
                database.get_session()
                .query(Package)
                .join(Class)
                .filter(Package.id.notin_(excl_packageids))
                .distinct()
                .all()
            )
        else:
            # If nothing is supplied return all model packages
            lst = database.get_session().query(Package).join(Class).distinct().all()
        if len(lst) == 0:
            logger.warning("Could not find any model packages to render ")
        return lst

    def getTemplateAndDir(self, args):  # sourcery skip: raise-specific-error
        # get templatedir to be used
        if self.templatedir is not None:
            templatedir = self.templatedir
        elif args.output_jinja2_templatedir is not None:
            templatedir = args.output_jinja2_templatedir
        else:
            templatedir = const.TEMPLATE_DIR
        if not os.path.isdir(templatedir):
            msg = f"Template directory with value {templatedir} does not exist, exiting"
            logger.error(msg)
            raise Exception(msg)
        logger.debug(f"Rendering with templatedir {templatedir}")

        # get template to be used
        if self.template is not None:
            template = self.template
        elif args.output_jinja2_template is not None:
            template = args.output_jinja2_template
        else:
            msg = "No template provided voor Jinja2, exiting"
            logger.error(msg)
            raise Exception(msg)
        logger.debug(f"Rendering with template {template}")
        return template, templatedir

    def render(self, args, database: db.Database):
        # setup output filename
        filename, extension = os.path.splitext(args.outputfile)

        # get template and templatedir
        template, templatedir = self.getTemplateAndDir(args)

        # sourcery skip: raise-specific-error
        # Settup environment for rendering using Jinja2
        file_loader = FileSystemLoader(templatedir)
        env = Environment(loader=file_loader)

        # Check to see if a list of Package ids is provided
        # if self.enforce_output_package_ids and args.output_package_ids is None:
        #    msg = "Usage of parameter --output_package_ids is enforced for this renderer. Not provided, exiting."
        #    logger.error(msg)
        #    raise Exception(msg)

        # Get list of packages that are to be rendered
        packages = self.getPackages(args, database)
        if len(packages) is None:
            msg = "Cannot render output: packages do not exist"
            logger.error(msg)
            raise Exception(msg)

        # Render all packages that are named
        for index, package in enumerate(packages):
            # Render output
            template = env.get_template(template)
            output = template.render(package=package, args=args)

            outputfilename = (
                f"{filename}_{package.name}{extension}"
                if package.name is not None
                else f"{filename}_{index}{extension}"
            )
            with open(outputfilename, 'w') as file:
                file.write(output)


@RendererRegistry.register(
    "ggm_md",
    descr='Renderer renders one basic markdown file per model in the database, '
    + 'where a model is a package that includes at least one Class. ',
)
class GGM_MDRenderer(Jinja2Renderer):
    template = 'ggm_markdown.j2'  # type: ignore
    enforce_output_package_ids = True  # Enforce list of Package ids
