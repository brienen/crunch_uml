import os
import shutil

import pytest


@pytest.fixture
def mock_function():
    pass


@pytest.fixture(scope="session", autouse=True)
def test_setup_output_directory():
    # Voorbereidingscode: Maak de directory aan
    output_dir = './test/output'
    os.makedirs(output_dir, exist_ok=True)
    yield  # Hier voeren de tests uit
    # Opruimcode: Verwijder de directory na de tests
    shutil.rmtree(output_dir)
