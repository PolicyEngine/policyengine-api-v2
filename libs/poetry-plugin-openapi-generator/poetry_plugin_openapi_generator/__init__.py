from pathlib import Path
import traceback
from cleo.commands.command import Command
from cleo.io.inputs.argument import Argument
from cleo.io.inputs.option import Option
from poetry.plugins.application_plugin import ApplicationPlugin
from openapi_python_client import generate
from openapi_python_client.parser.errors import ErrorLevel
from openapi_python_client.config import Config, ConfigFile, MetaType

class GenerateClientCommand(Command):
    name = "generate-python-client"
    description = "Generate Python client from OpenAPI spec"
    options = [
        Option(name="path", description="path to the openapi model", flag=False),
        Option(name="output-path", description = "directory to generate the client in", flag=False)
    ]
    
    def handle(self):
        spec_path = Path(self.option("path"))
        output_dir = Path(self.option("output-path"))

        self.io.output.write_line(f"Generating client into {output_dir} from {spec_path}")
        self.io.flush()
        config_file = ConfigFile()
        config = Config.from_sources(
            config_file=config_file, 
            meta_type=MetaType.POETRY,
            file_encoding="utf-8",
            overwrite=True,
            output_path=output_dir,
            document_source=spec_path
            )

        try:
            errors = generate(config=config)
        except Exception:
            self.io.error_output.write_line("Generation threw an exception")
            self.io.error_output.write_line(traceback.format_exc())
            raise


        all = [e for e in errors]
        for e in all:
            self.io.error_output.write_line(f"[{e.level}] {e.header}{e.detail if e.detail != None else ''}")
        at_error = [e for e in all if e.level == ErrorLevel.ERROR]
        if len(at_error) > 0:
            return 1
        return 0

def factory():
    return GenerateClientCommand()

class OpenapiPythonApplicationPlugin(ApplicationPlugin):
    def activate(self, application):
        application.command_loader.register_factory("generate-python-client", factory)
