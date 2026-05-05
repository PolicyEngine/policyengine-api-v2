import importlib
import sys


def test_gateway_models_import_does_not_import_fastapi_endpoints():
    module_names = [
        "fastapi",
        "src.modal.gateway",
        "src.modal.gateway.endpoints",
        "src.modal.gateway.models",
    ]
    previous_modules = {
        module_name: sys.modules.pop(module_name, None) for module_name in module_names
    }

    try:
        importlib.import_module("src.modal.gateway.models")

        assert "src.modal.gateway.endpoints" not in sys.modules
        assert "fastapi" not in sys.modules
    finally:
        for module_name in module_names:
            sys.modules.pop(module_name, None)
        sys.modules.update(
            {
                module_name: module
                for module_name, module in previous_modules.items()
                if module is not None
            }
        )
