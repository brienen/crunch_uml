import logging

import pandas as pd
import sqlalchemy
import os

from crunch_uml import db, const
from crunch_uml.renderers.renderer import Renderer, RendererRegistry
from jinja2 import Environment, FileSystemLoader
from crunch_uml.db import Package

logger = logging.getLogger()


def getPackages(args, database):
    lst = []
    # Get a list of package from args
    #if args.output_root_package_names is not None:
    #    packagenames = args.output_root_package_names.split(',')
    #    lst = database.get_session().query(Package).filter(Package.name.in_(packagenames)).all()
    #    if len(lst) == 0:
    #        logger.warning(f"Could not find any packages to render with list {args.output_root_package_names}")
    if args.output_root_packagen_ids is not None:
        packageids = args.output_root_packagen_ids.split(',')
        lst = database.get_session().query(Package).filter(Package.id.in_(packageids)).all()
        if len(lst) == 0:
            logger.warning(f"Could not find any packages to render with list {args.output_root_packagen_ids}")
    else:
        lst = database.get_session().query(Package).filter(Package.parent_package_id.is_(None)).all()
        if len(lst) == 0:
            logger.warning("Could not find any root packages to render")
    return lst

@RendererRegistry.register("jinja2")
class Jinja2Renderer(Renderer):
    templatedir = None
    template = None

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

        # Get list of packages that are to be rendered
        packages = getPackages(args, database)
        if len(packages) is None:
            msg = "Cannot render output: packages do not exist"
            logger.error(msg)
            raise Exception(msg) 

        # Render all packages that are named 
        for index, package in enumerate(packages):
            # Render output
            template = env.get_template(template)
            output = template.render(package=package, args=args)

            outputfilename = f"{filename}_{package.name}{extension}" if package.name is not None else f"{filename}_{index}{extension}"
            with open(outputfilename, 'w') as file:
                file.write(output)


@RendererRegistry.register("ggm_md")
class GGM_MDRenderer(Jinja2Renderer):
    template = 'ggm_markdown.j2'

