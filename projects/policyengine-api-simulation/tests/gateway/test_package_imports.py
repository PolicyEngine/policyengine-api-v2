import sys


def test_gateway_models_import_does_not_import_fastapi_endpoints(
    import_gateway_models,
    gateway_import_module_names,
):
    import_gateway_models()

    assert gateway_import_module_names.endpoints not in sys.modules
    assert gateway_import_module_names.fastapi not in sys.modules
