import logging

from openpyxl import Workbook

from crunch_uml import db
from crunch_uml.renderers.renderer import Renderer, RendererRegistry

logger = logging.getLogger()


@RendererRegistry.register("xlsx")
class XLSXRenderer(Renderer):
    def render(self, args, database: db.Database):
        wb = Workbook()
        wb.remove(wb.active)  # type: ignore # Remove default sheet

        # Retrieve all models dynamically
        base = db.Base
        models = base.metadata.tables
        session = database.get_session()

        for table_name, table in models.items():
            ws = wb.create_sheet(title=table_name)

            # Headers
            columns = [c.name for c in table.columns]
            for col_num, column in enumerate(columns, 1):
                ws.cell(row=1, column=col_num, value=column)

            # Model class associated with the table
            model = next(
                (
                    cls
                    for cls in base.registry._class_registry.values()
                    if hasattr(cls, '__table__') and cls.__table__ == table
                ),
                None,
            )

            if model:  # Ensure there's an associated model class
                # Data
                for row_num, record in enumerate(session.query(model).all(), 2):
                    for col_num, column in enumerate(columns, 1):
                        ws.cell(row=row_num, column=col_num, value=getattr(record, column))

        wb.save(args.output_file)
