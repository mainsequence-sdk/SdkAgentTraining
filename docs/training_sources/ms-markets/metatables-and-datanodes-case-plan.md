# ms-markets MetaTables and DataNodes Case Plan

This document plans future evaluation cases inspired by the `ms-markets`
reference implementation:

```text
repository: https://github.com/mainsequence-projects/MainSequenceMarkets
package: ms-markets
version: 0.0.71
ref: refs/tags/v0.0.71
```

No cases are created here. This is the design plan for what the cases should
teach and what makes them hard.

When converting this plan into cases, use the ms-markets git repository and a
pinned commit/ref plus repository-relative source files as
`case_source_of_truth`. This document and SDK skill snapshots are only
supporting context; they are not the truth source for a case inspired by an
implementation.

## Goal

Train and evaluate agents that can build Main Sequence projects with the same
architectural discipline as `ms-markets`.

The target behavior is not just producing code that imports. The agent must
choose the correct platform primitive, place responsibility in the correct
layer, and explain verification steps.

Core expected decisions:

- use MetaTables for durable relational or reference state
- use DataNodes for update processes that publish time-indexed facts
- define DataNode storage with `PlatformTimeIndexMetaTable`
- register storage and relational tables through SDK-managed MetaTable
  migrations
- keep runtime startup attach-only
- keep domain identity explicit and consistent

## Source Architecture To Teach

The reference project has three major layers.

- `msm`
  Core market primitives: assets, accounts, calendars, execution tables,
  repositories, services, and shared DataNode helpers.
- `msm_portfolios`
  Portfolio workflow layer: signal weights, portfolio values, portfolio
  weights, valuation-source dependencies, rebalance logic, and contributed
  price/signal nodes.
- `msm_pricing`
  Optional pricing layer: priceable instruments, pricing details, curves,
  fixings, market-data bindings, pricing resolvers, and valuation baskets.

The important pattern is that each layer narrows the generic Main Sequence SDK
rules without replacing them.

## Concepts That Must Be Tested

### MetaTables

A good case must test whether the agent understands that MetaTables are the
right primitive for row-oriented durable state.

Important concepts:

- `PlatformManagedMetaTable` for relational rows
- `MarketsMetaTableMixin` style project/domain mixins
- explicit `__metatable_identifier__`
- intention-rich `__metatable_description__`
- meaningful `info={"label": ..., "description": ...}` on every column
- project-prefixed physical names through shared naming helpers
- `schema=None` for default PostgreSQL schema, not `schema="public"`
- SQLAlchemy foreign keys for relationships
- unique indexes for business keys such as `unique_identifier`
- no manual backend UID threading in normal model declarations
- no runtime `.register()` for platform-managed tables
- compiled MetaTable operations for governed reads and writes

Relational structure is part of the contract, not an implementation detail.
Cases must require the agent to declare the table graph clearly.

Relational modeling requirements:

- state the row grain for every table before defining columns
- define a UUID primary key when rows need durable platform identity
- define a stable business key such as `unique_identifier`, `set_key`, or
  `signal_uid` when rows need idempotent upsert or external lookup
- add unique indexes or unique constraints for idempotent business keys
- add composite unique indexes for join or membership tables, such as
  `(portfolio_group_uid, portfolio_uid)` or `(market_data_set_uid, concept_key)`
- add lookup indexes for high-use filters such as foreign keys, status,
  concept key, asset type, source, or curve type
- use SQLAlchemy `ForeignKey` or `ForeignKeyConstraint` declarations on the
  model columns; do not describe relationships only in prose
- reference the correct target column, usually a durable `uid` for internal
  row ownership or a domain `unique_identifier` when the published contract is
  keyed by business identity
- choose `ondelete` behavior intentionally, usually `RESTRICT` for canonical
  reference rows and `CASCADE` only for dependent membership rows
- keep relationship rows separate from identity rows when the relationship has
  independent lifecycle or cardinality
- rely on SDK and SQLAlchemy naming helpers so constraints and indexes are
  deterministic and fit PostgreSQL identifier limits
- treat ORM `relationship(...)` as optional navigation convenience; the
  evaluation should score database-level foreign keys, indexes, and constraints
  first

Representative source ideas:

- `AssetTable` keyed by `unique_identifier`
- `CalendarTable`, `CalendarDateTable`, `CalendarSessionTable`
- `PortfolioTable` and portfolio group metadata
- `CurveTable`, `PricingMarketDataSetTable`,
  `PricingMarketDataSetBindingTable`

### DataNodes

A good case must test whether the agent understands that a DataNode is an
update process, not the canonical schema owner.

Important concepts:

- storage-first design with `PlatformTimeIndexMetaTable`
- DataNode constructor receives `config=...` and `storage_table=StorageClass`
- storage table owns `__time_index_name__`, `__index_names__`, cadence,
  columns, nullability, labels, descriptions, and foreign keys
- config carries update-scoped fields only
- DataNode identifiers/descriptions should derive from registered storage
  metadata when possible
- dependency graph is explicit and deterministic
- `update()` returns a DataFrame matching the storage contract
- first index dimension is the storage time index
- time index values must normalize to `datetime64[ns, UTC]`
- duplicate index rows are invalid
- incremental logic should use `UpdateStatistics`
- storage cleanup uses time-index delete APIs with explicit dimension scope
- raw SQL deletion or unscoped truncation is not acceptable

Representative source ideas:

- asset snapshots keyed by `(time_index, asset_identifier)`
- account holdings keyed by account, holdings set, asset, and timestamp
- signal weights keyed by `(time_index, signal_uid, asset_identifier)`
- portfolio values keyed by `(time_index, portfolio_identifier)`
- discount curves keyed by `(time_index, curve_identifier)`
- index fixings keyed by `(time_index, index_identifier)`
- external or interpolated prices keyed by `(time_index, asset_identifier)`

### MetaTable Migrations

A good case must test whether the agent knows that schema lifecycle belongs to
the SDK migration provider.

Important concepts:

- one SDK `AlembicMetaTableMigration` provider can cover multiple import roots
- model registry must be explicit and de-duplicated
- use SDK helper builders instead of hand-rolled Alembic provider logic
- run `mainsequence migrations current --provider ...`
- run `mainsequence migrations revision --provider ...`
- if `--autogenerate` is used, include the SDK-required explicit
  `--sqlalchemy-url` for the baseline database and explain why autogeneration is
  safe for that workflow
- run `mainsequence migrations upgrade --provider ... head`
- do not create separate providers for subpackages unless there is a real
  provider boundary
- runtime startup attaches already-registered MetaTables and must not create
  schema, apply migrations, or call `.register()`

Representative source idea:

- one provider named `migrations:migration` covers `msm`, `msm_portfolios`, and
  `msm_pricing`.

## What Makes These Tasks Difficult

These cases should be harder than simple "create a table" prompts. The
difficulty comes from boundary decisions and platform discipline.

Key difficulty dimensions:

- Choosing between MetaTable and DataNode when the user describes mixed
  reference data and time-series facts.
- Designing the relationship graph before writing models, including row grain,
  cardinality, ownership, and delete behavior.
- Keeping schema on the storage class instead of putting schema fields in
  `DataNodeConfiguration`.
- Creating correct foreign keys to business identity columns such as
  `AssetTable.unique_identifier`, `PortfolioTable.unique_identifier`,
  `CurveTable.unique_identifier`, and `IndexTable.unique_identifier`.
- Choosing between FK targets that should point to `uid` versus
  `unique_identifier`.
- Declaring composite unique indexes for relationship tables instead of relying
  on application-side duplicate checks.
- Avoiding stale names such as asset symbols or raw provider tickers as
  canonical dimensions.
- Knowing when a dynamic storage table needs
  `__metatable_extra_hash_components__`.
- Avoiding hidden dependency construction inside a downstream DataNode.
- Computing update windows from the required identity scope instead of the
  whole source table.
- Handling `APIDataNode` as a way to attach an already-registered table, not as
  an excuse to skip storage registration.
- Distinguishing runtime attachment from migration lifecycle.
- Writing verification steps that prove platform state exists rather than
  only claiming the code is correct.

## Planned Case Families

These are future case families, not implemented cases.

### Family 1: Relational Market Reference Data

Purpose: test MetaTable modeling.

Example task shape:

```text
Create durable reference tables for a market calendar, its sessions, and
calendar events. Explain why these are MetaTables and not DataNodes.
```

Expected agent behavior:

- choose MetaTables
- define the row grain and ownership of each table
- define table identifiers and descriptions
- add column labels and descriptions
- use foreign keys between calendar tables
- declare primary keys, business keys, unique indexes, and lookup indexes
- use `RESTRICT` or `CASCADE` intentionally based on lifecycle ownership
- include models in migration provider
- avoid runtime registration
- provide migration and verification commands

Common failure modes:

- modeling the calendar as a DataNode
- using raw SQL tables outside the SDK migration provider
- setting `schema="public"`
- missing column metadata
- describing relationships without SQLAlchemy foreign keys
- omitting composite uniqueness for child or membership rows
- using cascade delete on canonical rows where deletion should be restricted
- using application-side duplicate checks instead of database constraints

### Family 2: Asset-Indexed DataNode Storage

Purpose: test storage-first DataNode design.

Example task shape:

```text
Create a DataNode that publishes daily vendor risk scores for assets.
Rows are keyed by asset unique_identifier and observation time.
```

Expected agent behavior:

- define a `PlatformTimeIndexMetaTable` storage class
- use `asset_identifier` as the canonical dimension
- foreign-key `asset_identifier` to `AssetTable.unique_identifier`
- add any additional storage-table foreign keys required by the row grain
- declare `__time_index_name__`, `__index_names__`, and cadence
- do not manually duplicate the full-grain unique index already implied by the
  time-indexed storage contract
- keep vendor name and source file references out of canonical identity unless
  they affect storage or update identity
- normalize output to `datetime64[ns, UTC]`
- use `UpdateStatistics` for incremental updates

Common failure modes:

- using provider ticker as canonical identity
- putting index names in config
- creating duplicate `(time_index, asset_identifier)` rows
- returning naive datetimes

### Family 3: Portfolio Workflow With Explicit Dependencies

Purpose: test dependency graph discipline.

Example task shape:

```text
Build a portfolio DataNode that consumes signal weights and a valuation source
with valuation_column="fair_value".
```

Expected agent behavior:

- model signal weights and portfolio values as separate DataNodes
- pass valuation source explicitly through configuration
- expose dependencies as `signal_weights` and `valuation_source`
- avoid constructing interpolation or price DataNodes inside portfolio core
- validate that the valuation column exists
- derive required assets from signal output and prior weights

Common failure modes:

- forcing all valuation sources into OHLC `close`
- creating hidden `InterpolatedPrices` inside the portfolio DataNode
- using a static asset config as portfolio universe
- taking update-window progress across every source asset

### Family 4: Pricing Market-Data Bindings

Purpose: test MetaTable plus DataNode interaction.

Example task shape:

```text
Add pricing source selection for discount curves and index fixings.
```

Expected agent behavior:

- use MetaTables for named market-data sets and concept bindings
- store backend DataNode storage table UIDs in bindings
- use curve and fixing DataNodes for time-indexed observations
- read those sources with `APIDataNode.build_from_table_uid(...)`
- avoid static storage identifier constants as authoritative runtime pointers

Common failure modes:

- putting curve observations in `CurveTable`
- using constants as curve or fixing identity
- storing asset identity inside instrument payloads
- treating valuation baskets as persisted pricing positions

### Family 5: Dynamic Storage Identity

Purpose: test advanced storage identity and reproducibility.

Example task shape:

```text
Create interpolated price storage whose physical table identity depends on
source table UID, source cadence, upsample frequency, and interpolation rule.
```

Expected agent behavior:

- derive a configured storage class from source metadata
- set `__metatable_extra_hash_components__`
- keep policy fields out of table columns unless they are actual row data
- preserve asset FK and index contract
- declare cadence on the configured storage class
- expose the source price node as a dependency

Common failure modes:

- putting source UID and interpolation rule as row columns
- accepting arbitrary `storage_table` override when storage identity must be
  derived from config
- failing when source storage lacks cadence

### Family 6: Runtime Attachment Versus Migration

Purpose: test operational correctness.

Example task shape:

```text
You added a new storage class and row MetaTable. Explain the exact lifecycle
from model declaration to runtime startup.
```

Expected agent behavior:

- add the models to the migration provider registry
- run current/revision/upgrade with the correct provider
- start runtime only after backend resources exist
- attach models at startup
- fail clearly if backend MetaTables are missing

Common failure modes:

- calling `.register()` in app startup
- generating Alembic boilerplate manually
- creating separate providers for each subpackage without need
- claiming success without verifying registered resources

## Evaluation Signals

Rubrics should score both implementation choices and reasoning.

High-value positive signals:

- correct primitive choice
- correct ownership boundaries
- explicit row grain and relationship graph
- correct primary keys, business keys, foreign keys, and indexes
- explicit storage contracts
- explicit migration path
- rich metadata and labels
- deterministic dependencies
- correct identity dimensions
- scoped incremental update logic
- concrete verification steps

High-value negative signals:

- SimpleTable or legacy row-store patterns for SDK 4.x MetaTable tasks
- schema or FK declarations inside DataNode config
- relationships declared only in prose with no SQLAlchemy FK or constraint
- missing unique indexes for idempotent business keys or membership pairs
- wrong FK target, such as provider symbol instead of canonical UID or
  `unique_identifier`
- raw SQL for governed MetaTable operations
- runtime `.register()` or schema creation
- hidden DataNode dependency construction
- provider tickers or symbols used as canonical identity
- unscoped deletes
- missing `datetime64[ns, UTC]` normalization
- no platform verification plan

## Recommended Case Creation Order

Create cases in this order so the case bank grows from fundamentals to
composite workflows.

1. MetaTable reference model cases.
2. MetaTable migration lifecycle cases.
3. Simple asset-indexed DataNode storage cases.
4. DataNode validation and incremental update cases.
5. Portfolio explicit dependency cases.
6. Pricing curve/fixing and market-data binding cases.
7. Dynamic storage identity cases.
8. End-to-end mini-project cases combining MetaTables, DataNodes, migrations,
   and runtime attachment.

## Source Anchors

Use these source areas when converting this plan into actual cases:

- `src/msm/base.py`
- `src/migrations/__init__.py`
- `src/migrations/registry.py`
- `src/msm/models/assets/core.py`
- `src/msm/data_nodes/assets/asset_indexed.py`
- `src/msm/data_nodes/utils/stamped.py`
- `src/msm_portfolios/data_nodes/portfolios/__init__.py`
- `src/msm_portfolios/data_nodes/portfolios/storage.py`
- `src/msm_portfolios/data_nodes/signals/weights.py`
- `src/msm_portfolios/contrib/prices/data_nodes.py`
- `src/msm_pricing/models/market_data_bindings.py`
- `src/msm_pricing/data_nodes/curves/storage.py`
- `src/msm_pricing/data_nodes/index_fixings/storage.py`
- `docs/ADR/0022-alembic-metatable-migration-alignment.md`
- `docs/ADR/0030-explicit-portfolio-price-source-dependency.md`
- `docs/ADR/0031-generic-portfolio-valuation-source.md`
