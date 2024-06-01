import logging

from openpyxl import Workbook

import crunch_uml.schema as sch
from crunch_uml import db
from crunch_uml.renderers.renderer import Renderer, RendererRegistry

logger = logging.getLogger()


@RendererRegistry.register(
    "xlsx", descr='Renders Excel sheet where each tab corresponds to one of the tables in te datamodel.'
)
class XLSXRenderer(Renderer):
    def render(self, args, schema: sch.Schema):
        # sourcery skip: use-named-expression
        wb = Workbook()
        wb.remove(wb.active)  # type: ignore # Remove default sheet

        # Retrieve all models dynamically
        base = db.Base
        models = base.metadata.tables
        session = schema.get_session()

        for table_name, table in models.items():
            ws = wb.create_sheet(title=table_name)

            # Headers
            # columns = [c.name for c in table.columns]
            # Sort columns: 'id' first, then others alphabetically
            columns = ['id'] if 'id' in table.columns else []
            columns.extend(sorted([c.name for c in table.columns if c.name != 'id']))

            for col_num, column in enumerate(columns, 1):
                ws.cell(row=1, column=col_num, value=column)

            # Model class associated with the table
            model = base.model_lookup_by_table_name(table_name)

            if model:  # Ensure there's an associated model class
                # Data
                for row_num, record in enumerate(
                    session.query(model).filter(model.schema_id == schema.schema_id).all(), 2
                ):
                    for col_num, column in enumerate(columns, 1):
                        ws.cell(row=row_num, column=col_num, value=getattr(record, column))

        wb.save(args.outputfile)
