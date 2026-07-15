# CHANGELOG

## v0.5.1 (unreleased)

- **Import-run markers for shared databases.** Every `import` invocation records a row in a new `crunch_uml_runs` table (outside the ORM model, like `crunch_uml_meta`, so it never leaks into exports): `run_id`, `schema_id`, `started_at`, `crunch_version`, `datamodel_version`, and a `completed_at` that is stamped as the FINAL step after the import committed. A row with `completed_at` NULL marks an in-progress or aborted (torn) run — external readers of a shared crunch database (e.g. an import API) should only consume schemas whose latest run is completed. The markers use their own connection, so they survive a session rollback as evidence, and a database recreate clears them (the data they vouched for is gone).
- **Safe datamodel-version handling for shared databases.** New global flag `-on_version_mismatch {auto,fail,recreate}` controls what happens when a database was written with an incompatible datamodel version. `recreate` keeps the historical behaviour (drop and rebuild, all data discarded); `fail` stops with a clear error without touching the database; the default `auto` recreates only the local default database and fails on any explicitly provided `-db_url` — a mismatched crunch_uml version can no longer accidentally wipe a shared (staging) database.
- **PostgreSQL extra.** `pip install 'crunch_uml[postgres]'` installs the psycopg2 driver for `-db_url postgresql://...` staging workflows; documented in the import manual (NL/EN) together with the run-marker/version-policy contract.

## v0.5.0 (unreleased)

- **Datamodel version marker in the database.** Every crunch_uml database now stores a datamodel version in a `crunch_uml_meta` table (kept outside the ORM model so it never leaks into exports). On connect, a database with the same version — or one predating the marker — is migrated additively (missing tables/nullable columns are added, data kept); a database with a different version is incompatible and is recreated from scratch with a clear warning, after which models must be re-imported. The version is only bumped for schema changes the additive migration cannot handle.
- **All formats carry diagram geometry (phase 4).** The generic formats round-trip the four diagram junction tables including the geometry columns: `json`, `xlsx` and `csv` (one file/sheet per junction table); files written before these columns existed keep importing. The `i18n` format deliberately skips the junction tables (no `id` column, nothing translatable). The `earepo`/`eamimrepo` updaters now write diagram layout back to `t_diagramobjects` and `t_diagramlinks` — existing rows are updated, elements newly on a diagram are inserted, and membership that disappeared from the model is deleted, with the same coordinate conversions as the qea parser reversed; rows for element types crunch_uml does not manage (Notes, packages) and for elements unknown to the schema are left alone. A coverage matrix (parser/renderer × membership × geometry) was added to `docs/technisch/datamodel.md`. Version bumped to 0.5.0.
- **New XMI renderer (phase 3).** The new `xmi` renderer writes the complete schema as XMI 2.1 with an Enterprise Architect extension section — the mirror image of what the `eaxmi` parser reads: the strict `uml:Model` tree (packages, classes with attributes, enumerations with literals, associations with ends/cardinalities/roles, generalizations) plus the EA extension with documentation, project metadata, tagged values, connector roles and the diagrams including geometry (node rectangles regenerated with EA's positive-Top/Bottom convention, edge paths reassembled with the y-sign flip, `Hidden` folded back into the style string). The acceptance round-trip `parse → render → parse` yields a semantically identical schema — same entities, same diagram membership, byte-identical geometry — starting from `GGM_Monumenten_EA2.1.xml` (eaxmi), `Monumenten.qea` (qea), `Model Schuldhulpverlening.xml` (eaxmi) and `InkomenMIM.qea` (qea, with datatypes and named/stereotyped generalizations). Generalization connectors are written to (and now also read from) the EA extension so their name/definition/stereotype survive; association stereotypes travel as a tagged value; classes without a (known) package are placed in the first root package instead of being dropped; XML-incompatible control characters are stripped with a warning. EA-specific deviations are documented in `crunch_uml/renderers/EA_QUIRKS.md`; a manual import check in Sparx EA is still pending. The `eaxmi` parser now also reads extension data for `uml:DataType` elements, and the `qea` parser normalizes Windows line endings in Notes/tagged values to LF — the XML spec forces that normalization on attribute values, so both parsers now yield byte-identical text for the same model.
- **Parsers read diagram geometry (phase 2).** The `eaxmi` parser now parses the `geometry` attribute of diagram elements: node positions/sizes from `Left/Top/Right/Bottom`, `seqno` as z-order, edge waypoints from `Path=` (with the EA y-sign flip), the `Hidden` flag from the style string, and the raw EA style/geometry strings losslessly. The `qea` parser gains a new phase that reads `t_diagram`, `t_diagramobjects` and `t_diagramlinks`, adding the previously missing diagram membership for `.qea` imports plus the same canonical geometry (RectTop/RectBottom are negative in the QEA database). Both parsers normalize to one canonical database form, verified by a cross-check test: the same model imported through `eaxmi` and `qea` yields identical geometry rows. Duplicate occurrences of one element on one diagram (rare, allowed by EA) are logged and the first instance wins; Notes, constraints and other unsupported element types are skipped as before. The new `crunch_uml.ea_geometry` module holds all conversions.
- **Diagram geometry in the data model (phase 1).** The four diagram junction tables now carry layout information alongside membership: node-like members (`diagram_class`, `diagram_enumeration`) get nullable `x`, `y`, `width`, `height`, `z_order` and `ea_style` columns; edge-like members (`diagram_association`, `diagram_generalization`) get nullable `waypoints` (JSON), `hidden`, `ea_geometry` and `ea_style` columns. Coordinates are stored in a canonical system (origin top-left, y downwards, all positive); parsers/renderers convert at the edge. `Diagram.get_copy()` now copies the geometry along and also copies association/generalization membership, which was previously omitted; membership is only copied for relations that actually end up in the copy (mirroring the conditions of `Class.get_copy`, evaluated against the owning class's own root scope), so no dangling rows are created. `Package` additionally gains the `get_associations_inscope`/`get_generalizations_inscope` helpers that `Diagram.get_instances` referenced but that never existed. Existing database files from older versions are migrated on connect with a lightweight additive step (missing tables and nullable columns are added, nothing is dropped), and the pandas-based parsers now normalize NaN from empty spreadsheet cells to NULL so typed columns accept them.

## v1.9.1 (2023-05-08)

- Fixes a replacement typo in setup.py for `package_data`
- Bumps all dependencies

## v1.9.0 (2022-11-02)

- Removes the `coveralls` dev dependency and instead updates `pytest-cov` to v4 which now supports `lcov` generation

## v1.8.0 (2022-05-15)

- Overhaul the build process (uses the `build` package instead of the legacy `python setup.py` command)
- Simplifies the GitHub release workflow by using the new Makefile build targets
- Ignores the test directory in the build
- Pins all development dependencies

## v1.7.1 (2022-02-10)

- Update Makefile install target to not symlink to the home directory
- Update Black to use the `preview` flag
- Bump dev dependencies

## v1.7.0 (2021-11-29)

- Adds `mypy` and type hinting via `py.typed`
- Simplifies template module (removes unused class)
- Adds missing `__all__` variable to `__init__.py`
- Simplifies the lint step of the build by only running checks once (previously some checks were getting run twice)
- Tests against Python `3.10`

## v1.6.0 (2021-10-08)

- Adds `Black` and `iSort` as dev dependencies
- Adds a `pyproject.toml` file to configure Python tools
- Completely refactors the `Makefile` to include new tools and better ways of invoking previous ones
- Removes `.github/FUNDING.yml` file in favor of `.github` global files

## v1.5.0 (2021-09-10)

- Drops support for Python 3.6
- Removes the `mock` library in favor of the builtin `unittest.mock` library
- Fix some typos

## v1.4.0 (2021-07-12)

- Clarified various pieces of info
- Unified more text replacements for easier usage of the template when getting started

## v1.3.0 (2021-05-31)

- Pins dependencies and moves them to a constant
- Adds missing lines to code coverage report

## v1.2.0 (2021-01-30)

- Fixed the Coveralls command in GitHub Actions, builds now pass with their new platform requirement flag
- Added a `release.yml` file to automate PyPI releasing via GitHub Actions

## v1.1.1 (2021-01-09)

- Removed all references to Travis-CI and replace with GitHub Actions
- Bumped the year in LICENSE
- Added clarifying statement in README to remove all extra assets

## v1.1.0 (2021-01-05)

- Added GitHub Actions
- Added `conftest.py`
- Updated `README` with much more verbose instructions on changing details of the project to get you started
- Added test coverage
- Correcting lint Makefile target to point to the unit folder

## v1.0.0 (2020-11-19)

- Initial release
- Makefile, README, setup.py, .travis.yml, LICENSE, test suite, module, assets, and more included to save time and energy on your next Python project
