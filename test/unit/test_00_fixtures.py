import os
import shutil
import pytest

@pytest.fixture(scope="session", autouse=True)
def setup_output_directory():
    # Voorbereidingscode: Maak de directory aan
    output_dir = './test/data/output'
    os.makedirs(output_dir, exist_ok=True)
    yield  # Hier voeren de tests uit
    # Opruimcode: Verwijder de directory na de tests
    shutil.rmtree(output_dir)
