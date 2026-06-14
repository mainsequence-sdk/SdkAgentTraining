---
name: mainsequence-simple-tables
description: Use this skill when the task is about defining, changing, querying, or reviewing Main Sequence SimpleTables and SimpleTableUpdaters. This skill owns row schemas, backend-managed ids, insert versus overwrite behavior, filtering, foreign keys, and validation rules. It does not own DataNode producers, API route contracts, scheduling, or sharing policy.
---

# Main Sequence SimpleTables

## Overview

Use this skill when the task changes row-oriented project tables that are not naturally time-series DataNodes.

This skill is for schema-driven application tables and their updater workflows.

## This Skill Can Do

- create a new `SimpleTable`
- create or modify a `SimpleTableUpdater`
- define indexes, foreign keys, and `Ops(...)`
- design typed filter expressions
- design join filters across simple tables
- decide whether a write should be insert-only or overwrite/upsert
- review simple-table code for invalid `id` usage
- review whether a task should be a SimpleTable or a DataNode

## This Skill Must Not Claim

This skill must not claim ownership of:

- DataNode producer contracts
- FastAPI route contracts
- widget response contracts
- workspace payloads
- job scheduling, image pinning, or releases
- RBAC or sharing policy

If the user is still in the discovery process and does not yet know what data exists on the platform, use the exploration skill first and return here after discovery is complete.

## Route Adjacent Work

- discovery-only data inventory before SimpleTable implementation:
  `.agents/skills/data_access/exploration/SKILL.md`
- DataNodes:
  `.agents/skills/data_publishing/data_nodes/SKILL.md`
- APIs and FastAPI:
  `.agents/skills/application_surfaces/api_surfaces/SKILL.md`
- Command Center workspaces:
  `.agents/skills/command_center/workspace_builder/SKILL.md`
- AppComponents and custom forms:
  `.agents/skills/command_center/app_components/SKILL.md`
- Jobs, images, resources, and releases:
  `.agents/skills/platform_operations/orchestration_and_releases/SKILL.md`

## Read First

1. `docs/tutorial/working_with_simple_tables.md`
2. `docs/knowledge/simple_tables/simple_table.md`
3. `docs/knowledge/simple_tables/filtering.md`

## Inputs This Skill Needs

Before changing code, collect or infer:

- the row entities that should exist
- the business keys
- relation shape between tables
- expected read patterns
- expected mutation patterns
- whether rows already exist or are being seeded for the first time

If the mutation model is unclear, stop before choosing insert-only versus overwrite.

## Required Decisions

For every non-trivial task, decide:

1. Is this table really row-oriented, or should it be a DataNode?
2. What is the business key?
3. Does the backend mutation require row ids?
4. Is this write insert-only or overwrite/upsert?
5. Are foreign-key dependencies aligned with the intended insert/read flow?

## Build Rules

### 1. `SimpleTable` defines schema, `SimpleTableUpdater` owns the real table

Keep that split clear.

Do not mix row schema concerns with backend updater concerns.

### 2. `SimpleTable` schema rules are hard constraints

For authored schemas:

- the row model must subclass `SimpleTable`
- users must not declare `id`
- the schema must not rely on undeclared extra fields
- logical and physical column names must be `63` characters or fewer

Per-field metadata must also follow the active SDK contract:

- `ForeignKey.target` must be a non-empty dependency key
- `ForeignKey.on_delete` must be one of:
  - `cascade`
  - `restrict`
  - `set_null`
- a field must not declare multiple `ForeignKey` metadata entries
- a field must not declare multiple `Index` metadata entries
- a field must not declare multiple `Ops` metadata entries

### 3. `SimpleTableUpdater` construction rules are hard constraints

For updater implementations:

- the updater must subclass `SimpleTableUpdater`
- `SIMPLE_TABLE_SCHEMA` must be defined
- `SIMPLE_TABLE_SCHEMA` must be a `SimpleTable` subclass
- updater configuration must use `SimpleTableUpdaterConfiguration` / `BaseConfiguration`

Do not use removed hashing patterns such as:

- `_ARGS_IGNORE_IN_STORAGE_HASH`
- `init_meta`
- `ignore_from_storage_hash`

Use current Pydantic field metadata rules:

- updater-scope-only config fields should use `json_schema_extra={"update_only": True}`
- descriptive runtime-only config fields should use `json_schema_extra={"runtime_only": True}`
- no config field may be both `update_only` and `runtime_only`

### 4. `id` is backend-managed

Users must not declare `id` in a `SimpleTable` subclass.

The normal lifecycle is:

1. insert without `id`
2. read rows back
3. use returned `id` values for sparse updates, upserts, or deletes

### 5. Unique index is not overwrite key

A unique business key is useful for lookup and constraints.

It is not the backend mutation key for overwrite/upsert payloads.

If `update()` returns `(records, True)`, those records must already include backend ids.

### 6. `update()` return rules are hard constraints

On the default updater path:

- `update()` must not return `None`
- `update()` must return either:
  - a sequence of `SIMPLE_TABLE_SCHEMA` instances
  - `(sequence_of_schema_instances, overwrite_bool)`
- returned records must be instances of the declared schema

Do not return:

- raw dict payloads
- DataFrames
- mixed record types

Those are not the default `SimpleTableUpdater.update()` contract.

### 7. Insert-only is the default when ids do not exist yet

Use insert-only when:

- seeding rows
- loading new records
- the records do not yet carry backend ids

### 8. Foreign-key targets must resolve through real updater dependencies

If the schema declares `ForeignKey("some_dependency_key")`:

- that key must resolve through `dependencies()`
- the resolved dependency must be a `SimpleTableUpdater`
- a foreign key must not point to the updater itself
- cyclic simple-table foreign-key resolution is invalid

### 9. Filters come from the schema and execute through the updater

Build filter expressions from the schema surface.

Execute them through the updater.

Do not bypass the updater with hand-built backend table requests.

Typed filter and join rules are also hard constraints:

- filter expressions must only use fields allowed by `Ops.filter=True`
- ordering keys must only use fields allowed by `Ops.order=True`
- simple-table requests must target a concrete `storage_hash`
- simple-table joins must target a concrete `storage_hash`
- simple-table joins must not use `node_unique_identifier`
- `joins=` must contain only `JoinSpec` or `JoinHandle`

### 10. Foreign keys must reflect actual dependency flow

If one table depends on another:

- parent rows must exist first
- child rows should use the returned backend ids from the parent

## Review Rules

When reviewing an existing SimpleTable workflow, look for:

- user-declared `id`
- overlength logical or physical column names
- invalid or duplicated field metadata
- treating a business key as the overwrite key
- missing `SIMPLE_TABLE_SCHEMA`
- invalid updater configuration or removed hashing patterns
- `update()` returning `None`, dicts, or other invalid payloads
- overwrite/upsert without backend ids
- foreign keys that do not match the real dependency flow
- foreign-key targets not declared in `dependencies()`
- self-referential or cyclic foreign-key resolution
- filters bypassing the typed schema surface
- filters or ordering on fields that were not declared operationally valid
- a table that should really be modeled as a DataNode instead

## Validation Checklist

Do not claim success until you have checked:

- the schema matches the intended row contract
- `id` is not user-declared
- column names are valid
- indexes are intentional
- field metadata is valid
- `SIMPLE_TABLE_SCHEMA` is defined correctly
- updater config metadata is classified correctly
- foreign keys point to the correct dependency targets
- insert-only versus overwrite behavior is correct
- `update()` returns typed schema instances
- overwrite/upsert payloads include backend ids when required
- filters run through the updater
- filters and ordering only use allowed fields

For join filters, also check:

- aliases are readable
- resolved tables are used intentionally
- joins use valid simple-table join semantics
- the base row type returned by the updater is still the expected one

## This Skill Must Stop And Escalate When

- a proposed schema declares `id`
- field names or metadata violate the SDK schema contract
- overwrite/upsert is attempted without backend ids
- `update()` return shape is unclear or invalid
- foreign-key dependency resolution is unclear
- the task really requires a time-series published table
- the workflow requires a richer relational model than `SimpleTable` is meant to support
- the task is actually an API or orchestration problem

Do not guess through mutation semantics.
