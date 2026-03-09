# Vulnerabilities & Technical Debt

## Risk Matrix

| Risk | Likelihood | Impact | Score | Component | Mitigation |
|---|:---:|:---:|:---:|---|---|
| XMI parsing errors due to source diversity | High | High | **9** | XMI Parser, EA XMI Parser | Encoding detection, recovery, error logging |
| Inconsistencies repository vs. actual metaschema | High | High | **9** | Centralized Repo (planned) | Schema validation, version tracking |
| Memory burden indexed data | High | Medium | **6** | Indexing (planned) | Lazy loading, pagination, streaming |
| Concurrency issues cache/validation | Medium | High | **6** | Caching Engine (planned) | Locking strategy, versioned cache |
| Complexity mapping configuration | Medium | Medium | **4** | Mapping Layer (planned) | DSL, test-driven development |
| Singleton pattern with concurrent usage | Low | Medium | **3** | Database class | Connection pooling |
| Destructive EA Repo operations | Low | High | **3** | EA Repo Updater | Flags, dry-run mode |

---

## High Risk

### XMI Parsing — Error Sensitivity

Parsing XMI data is vulnerable due to diversity in source formats and repositories. Each source system has its own structure, resulting in error-prone parsing. The two-phase approach (structure → relationships) reduces this but does not eliminate it.

**Impact**: Data loss, inconsistent models

**Current Mitigation**: Encoding detection, recovery mechanisms, comprehensive error logging

!!! danger "Core Problem"
    Due to limited support for XMI in Python libraries, all XMI libraries must be developed in-house. This leads to reduced efficiency and increased risk of unrecoverable errors.

### Metaschema Inconsistencies

The risk that the repository metaschema deviates from the metaschemas actually used in source systems.

**Impact**: Incorrect interpretations of data structures

**Current Mitigation**: Not fully addressed yet — planned solution via centralized repository with hierarchy documentation.

---

## Medium Risk

### Validation Overhead

Repeated validations with incomplete relationships require significant computing power. There is currently no caching of validation results.

**Impact**: Unacceptable delays with large models

**Planned Mitigation**: Caching & Validation Engine with:

- [ ] Cache mechanism for stored validations
- [ ] Control module for managing cached results
- [ ] Concurrent-safe cache invalidation

### Inheritance Interpretation Variations

Diversity in how inheritance relationships are modeled and interpreted when translating to physical database models.

**Impact**: Inconsistent output with complex models

**Planned Mitigation**: Universal Mapping Layer with standard strategies

### Singleton Database Pattern { #singleton-database-pattern }

The Database class uses a singleton pattern that can be problematic with multi-threaded or concurrent usage. There is no connection pooling or thread-safety handling.

**Impact**: Concurrency issues, potential memory leaks

**Possible Mitigation**:

- [ ] SQLAlchemy session-per-request pattern
- [ ] Connection pooling configuration
- [ ] Thread-local sessions

---

## Low Risk

### EA Repo Updater — Destructive Operations

The EA Repo Updater can add and delete records in production EA repositories via `--ea_allow_insert` and `--ea_allow_delete`.

**Impact**: Potentially unrecoverable data loss

**Current Mitigation**: Flags behind CLI arguments, documentation

**Additional Suggestions**:

- [ ] Dry-run mode (`--ea_dry_run`)
- [ ] Automatic backup for changes
- [ ] Confirmation prompt for destructive operations

### Translators Library — External Dependency

The translation module (lang.py) depends on the `translators` library. External services may become unavailable or impose rate limits.

**Impact**: Failing i18n exports

**Current Mitigation**: Retry logic, fallback translator

### Large db.py (1200+ lines)

The database model file combines model definitions, business logic and helper methods in one file.

**Impact**: Increased maintenance burden

**Suggestion**:

- [ ] Split into `models/package.py`, `models/clazz.py`, etc.
- [ ] Move business logic to service layer
- [ ] Extract mixins to separate file
