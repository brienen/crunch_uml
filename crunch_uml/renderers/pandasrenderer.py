import logging

import pandas as pd
import sqlalchemy

from crunch_uml import db
from crunch_uml.renderers.renderer import Renderer, RendererRegistry

logger = logging.getLogger()

def object_as_dict(obj):
    """Converts a SQLAlchemy model object to a dictionary, excluding private attributes."""
    return {c.key: getattr(obj, c.key) for c in sqlalchemy.inspect(obj).mapper.column_attrs}


@RendererRegistry.register("json")
class JSONRenderer(Renderer):
    def render(self, args, database: db.Database):
        # Retrieve all models dynamically
        base = db.Base
        models = base.metadata.tables
        session = database.get_session()
        all_data = {}

        for table_name, table in models.items():
            # Model class associated with the table
            model = next(
                (
                    cls
                    for cls in base.registry._class_registry.values()
                    if hasattr(cls, '__table__') and cls.__table__ == table
                ),
                None,
            )
            # Retrieve data
            records = session.query(model).all()
            df = pd.DataFrame([object_as_dict(record) for record in records])

            all_data[table_name] = df.to_dict(orient='records')

        with open(args.outputfile, "w") as json_file:
            import json
            json.dump(all_data, json_file, default=str)