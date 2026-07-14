import os
import shutil

import pytest

import crunch_uml.const as const


@pytest.fixture
def mock_function():
    pass


@pytest.fixture(scope="session", autouse=True)
def isolated_test_database(tmp_path_factory):
    """Run the whole suite against a database file outside the repository.

    The repository may live in a cloud-synced folder (kDrive); the sync
    daemon briefly locks files it uploads, which makes SQLite writes fail
    with 'database is locked'. The CLI then rolls back the affected import
    and continues, so later tests see empty or stale schemas — flaky,
    hard-to-reproduce failures. A unique file in the system temp directory
    sidesteps the sync entirely and also isolates concurrent test runs.

    Everything reads the URL via ``const.DATABASE_URL`` at call time (the
    CLI builds its argument parser per invocation), so patching the constant
    before the first test is sufficient.
    """
    db_path = tmp_path_factory.mktemp("crunch_uml_db") / "crunch_uml_test.db"
    original_url = const.DATABASE_URL
    const.DATABASE_URL = f"sqlite:///{db_path}"
    yield
    const.DATABASE_URL = original_url


@pytest.fixture(scope="session", autouse=True)
def test_setup_output_directory():
    # Voorbereidingscode: Maak de directory aan
    output_dir = "./test/output"
    os.makedirs(output_dir, exist_ok=True)
    yield  # Hier voeren de tests uit
    # Opruimcode: Verwijder de directory na de tests
    shutil.rmtree(output_dir)
