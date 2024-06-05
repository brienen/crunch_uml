import importlib.util
import logging
import os
import sys

from crunch_uml.exceptions import CrunchException
from crunch_uml.transformers.plugin import Plugin
from crunch_uml.transformers.transformer import Transformer, TransformerRegistry

logger = logging.getLogger()


@TransformerRegistry.register(
    "plugin", descr='Writes the content from one schema to another using a dynamicly loaded plugin.'
)
class PluginTransformer(Transformer):
    def load_plugin_dynamically(self, plugin_path, plugin_class_name):
        logger.debug(f"Dynamically loading class {plugin_class_name} from module at {plugin_path}")

        if not os.path.exists(plugin_path):
            msg = f"Error: The module path '{plugin_path}' does not exist."
            logger.error(msg)
            raise CrunchException(msg)

        module_name = os.path.splitext(os.path.basename(plugin_path))[0]

        try:
            spec = importlib.util.spec_from_file_location(module_name, plugin_path)
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)
        except Exception:
            msg = f"Error: Could not load module from path '{plugin_path}'."
            logger.error(msg)
            raise CrunchException(msg)

        try:
            # Gebruik getattr om de klasse uit de dynamisch geladen module te halen
            plugin = getattr(module, plugin_class_name)
        except AttributeError:
            msg = f"Error: Class '{plugin_class_name}' could not be found in module '{module_name}'."
            logger.error(msg)
            raise CrunchException(msg)

        # Controleer of de geladen klasse een subtype is van de parentclass
        if not issubclass(plugin, Plugin):
            msg = f"Error: Class '{plugin_class_name}' is not a subclass of '{Plugin.__name__}'."
            logger.error(msg)
            raise TypeError(msg)

        return plugin

    def transformLogic(self, args, root_package, schema_from, schema_to):
        if not args.plugin_file_name:
            raise CrunchException("Error: no module provided for plugin, --plugin_file_name needs to have value.")
        if not args.plugin_class_name:
            raise CrunchException("Error: no class provided for plugin, --plugin_class_name needs to have value.")
        MyPlugin = self.load_plugin_dynamically(args.plugin_file_name, args.plugin_class_name)
        plugin = MyPlugin()
        plugin.transformLogic(args, root_package, schema_from, schema_to)
