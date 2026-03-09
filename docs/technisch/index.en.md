# Technical Design

This part of the documentation describes the internal architecture, components, and technical design of crunch_uml. It is intended for developers working on crunch_uml or wanting to extend it.

## Architecture Diagram

![Architecture Overview](../image/01_architectuur.drawio.svg)

## Overview

crunch_uml is built as a **plugin-based, registry-driven architecture** with six layers:

1. **Presentation Layer** — CLI interface, logging, constants
2. **Orchestration Layer** — Registry pattern and plugin framework
3. **Import Layer** — 8 parsers for various input formats
4. **Transformation Layer** — Copy transformer and plugin framework
5. **Export Layer** — 22 renderers for various output formats
6. **Persistence Layer** — SQLAlchemy ORM with multi-schema support

## Sections

| Section | Content |
|---|---|
| [Architecture](architectuur/index.md) | Layer model, dataflows, design patterns |
| [Components](componenten/index.md) | Parsers, transformers, renderers, persistence |
| [Data Model](datamodel.md) | ORM entities, relationships and multi-schema operation |
| [Vulnerabilities](kwetsbaarheden.md) | Technical risks and mitigation |
| [Roadmap](roadmap.md) | Planned components and further development |
| [Technical Stack](stack.md) | Dependencies and tooling |
