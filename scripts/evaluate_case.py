from __future__ import annotations

import argparse
import ast
import datetime as dt
import json
import re
from pathlib import Path
from typing import Any

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
PYTHON_BLOCK_RE = re.compile(r"```(?:python)?\n(.*?)```", re.DOTALL | re.IGNORECASE)

DATANODE_QUALITY_WEIGHTS = {
    "dataset-contract": 0.18,
    "incremental-update": 0.18,
    "dependency-design": 0.16,
    "metadata-quality": 0.16,
    "asset-index-discipline": 0.12,
    "testing-isolation": 0.1,
    "dataframe-hygiene": 0.1,
}

SIMPLETABLE_QUALITY_WEIGHTS = {
    "table-choice-and-scope": 0.14,
    "schema-design-quality": 0.18,
    "id-mutation-workflow": 0.16,
    "foreign-key-workflow-quality": 0.14,
    "updater-design": 0.12,
    "filtering-and-join-design": 0.14,
    "operational-clarity": 0.12,
}

SIMPLETABLE_UPDATER_QUALITY_WEIGHTS = {
    "updater-responsibility-clarity": 0.12,
    "dependency-design": 0.16,
    "foreign-key-workflow-quality": 0.14,
    "insert-vs-overwrite-judgment": 0.16,
    "id-lifecycle-clarity": 0.14,
    "filter-and-join-workflow-quality": 0.12,
    "configuration-quality": 0.08,
    "operational-completeness": 0.08,
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Evaluate a saved model response for one case.")
    parser.add_argument("--case-path", type=Path, required=True, help="Path to the case directory.")
    parser.add_argument("--response-path", type=Path, required=True, help="Path to the saved response.md file.")
    parser.add_argument(
        "--evaluator-name",
        default="codex-heuristic-v1",
        help="Name of the evaluator recorded in the evaluation JSON.",
    )
    parser.add_argument(
        "--evaluator-kind",
        default="rule-based",
        help="Evaluator kind, for example rule-based, llm-judge, or human-review.",
    )
    parser.add_argument(
        "--output-path",
        type=Path,
        help="Optional path for the evaluation JSON. Prints to stdout when omitted.",
    )
    return parser


def load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def contains_all(text: str, patterns: list[str]) -> bool:
    return all(pattern in text for pattern in patterns)


def contains_any(text: str, patterns: list[str]) -> bool:
    return any(pattern in text for pattern in patterns)


def extract_python_blocks(text: str) -> list[str]:
    return [match.strip() for match in PYTHON_BLOCK_RE.findall(text)]


def dotted_name(node: ast.AST | None) -> str:
    if node is None:
        return ""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = dotted_name(node.value)
        return f"{prefix}.{node.attr}" if prefix else node.attr
    if isinstance(node, ast.Call):
        return dotted_name(node.func)
    return ""


def string_constant(node: ast.AST | None) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def bool_constant(node: ast.AST | None) -> bool | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, bool):
        return node.value
    return None


def find_keyword(call: ast.Call, keyword_name: str) -> ast.AST | None:
    for keyword in call.keywords:
        if keyword.arg == keyword_name:
            return keyword.value
    return None


def int_constant(node: ast.AST | None) -> int | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, int):
        return node.value
    return None


class DataNodeResponseAnalyzer:
    def __init__(self, response_text: str):
        self.response_text = response_text
        self.lowered = response_text.lower()
        self.python_blocks = extract_python_blocks(response_text)
        self.code_text = "\n\n".join(self.python_blocks)
        self.parse_errors: list[str] = []
        self.trees: list[ast.AST] = []

        self.data_node_classes: list[str] = []
        self.config_classes: list[str] = []
        self.has_super_init_config = False
        self.uses_removed_legacy_patterns = False
        self.invalid_hash_metadata: list[str] = []
        self.update_only_fields: list[str] = []
        self.runtime_only_fields: list[str] = []

        self.has_update_method = False
        self.update_returns_none = False
        self.update_calls_dataframe = False
        self.uses_update_statistics = False
        self.uses_offset_start = False
        self.explicit_full_history_pattern = False

        self.has_dependencies_method = False
        self.dependencies_return_dict = False
        self.dependencies_in_init = False
        self.dependencies_built_in_update = False
        self.dependency_keys: list[str] = []

        self.uses_node_metadata = False
        self.uses_records = False
        self.uses_identifier = False
        self.uses_record_definition = False
        self.uses_get_table_metadata = False
        self.uses_get_column_metadata = False

        self.uses_hash_namespace = False
        self.uses_test_node = False

        self.uses_asset_list = False
        self.uses_get_asset_list = False
        self.uses_unique_identifier = False
        self.uses_asset_symbol = False
        self.uses_multiindex = False
        self.uses_asset_registration = False

        self.column_names: list[str] = []
        self.column_names_too_long: list[str] = []
        self.uppercase_column_names: list[str] = []
        self.uses_time_index = False
        self.index_names_seen: list[str] = []
        self.uses_datetime_payload_column = False
        self.uses_drop_duplicates = False
        self.mentions_duplicate_safe = False
        self.mentions_stable_dtypes = False
        self.mentions_sorted_index = False

        self._parse()
        self._scan_text()
        self._analyze_trees()
        self._finalize_columns()

    def _parse(self) -> None:
        for index, block in enumerate(self.python_blocks, start=1):
            try:
                self.trees.append(ast.parse(block))
            except SyntaxError as exc:
                self.parse_errors.append(f"python block {index}: {exc.msg} line {exc.lineno}")

    def _scan_text(self) -> None:
        lowered = self.lowered
        self.uses_removed_legacy_patterns = contains_any(
            lowered,
            ["_args_ignore_in_storage_hash", "init_meta", "ignore_from_storage_hash"],
        )
        self.has_super_init_config = "super().__init__(config=" in self.code_text or "super().__init__(config=" in lowered
        self.uses_update_statistics = "update_statistics" in lowered
        self.uses_offset_start = "offset_start" in lowered
        self.explicit_full_history_pattern = contains_any(
            lowered,
            [
                "fetch full history every run",
                "return full history every run",
                "load all history every run",
                "read the full table each run",
            ],
        )
        self.uses_node_metadata = contains_any(lowered, ["node_metadata", "datanodemetadata"])
        self.uses_records = contains_any(lowered, ["records", "recorddefinition"])
        self.uses_record_definition = "recorddefinition" in lowered
        self.uses_get_table_metadata = "get_table_metadata" in lowered
        self.uses_get_column_metadata = "get_column_metadata" in lowered
        self.uses_identifier = "identifier" in lowered
        self.uses_hash_namespace = "hash_namespace" in lowered
        self.uses_test_node = "test_node" in lowered
        self.uses_asset_list = "asset_list" in lowered
        self.uses_get_asset_list = "get_asset_list" in lowered
        self.uses_unique_identifier = "unique_identifier" in lowered
        self.uses_asset_symbol = "asset_symbol" in lowered
        self.uses_multiindex = "multiindex" in lowered
        self.uses_asset_registration = contains_any(
            lowered,
            [
                "batch_get_or_register_custom_assets",
                "get_or_register_custom_assets",
                "register_custom_assets",
            ],
        )
        self.uses_time_index = "time_index" in lowered
        self.uses_datetime_payload_column = "datetime64" in lowered
        self.uses_drop_duplicates = "drop_duplicates" in lowered
        self.mentions_duplicate_safe = contains_any(
            lowered,
            [
                "no duplicate",
                "no duplicate rows",
                "no duplicate (time_index, unique_identifier)",
                "no duplicate index",
            ],
        )
        self.mentions_stable_dtypes = "stable dtype" in lowered or "stable dtypes" in lowered
        self.mentions_sorted_index = "sorted ascending" in lowered or "sort_index" in lowered

    def _analyze_trees(self) -> None:
        for tree in self.trees:
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    self._analyze_class(node)
                elif isinstance(node, ast.Call):
                    self._analyze_global_call(node)

    def _analyze_class(self, node: ast.ClassDef) -> None:
        base_names = {dotted_name(base).split(".")[-1] for base in node.bases}
        is_data_node = "DataNode" in base_names
        is_config = bool(base_names & {"DataNodeConfiguration", "BaseConfiguration"})

        if is_data_node:
            self.data_node_classes.append(node.name)
        if is_config:
            self.config_classes.append(node.name)

        if is_config:
            for stmt in node.body:
                self._analyze_config_stmt(stmt)

        if is_data_node:
            for stmt in node.body:
                if isinstance(stmt, ast.FunctionDef):
                    self._analyze_node_method(stmt)

    def _analyze_config_stmt(self, stmt: ast.stmt) -> None:
        if not isinstance(stmt, ast.AnnAssign):
            return
        if not isinstance(stmt.target, ast.Name):
            return
        field_name = stmt.target.id
        call = stmt.value
        if not isinstance(call, ast.Call):
            return
        if dotted_name(call.func).split(".")[-1] != "Field":
            return

        json_schema_extra = find_keyword(call, "json_schema_extra")
        update_only = None
        runtime_only = None
        if isinstance(json_schema_extra, ast.Dict):
            for key_node, value_node in zip(json_schema_extra.keys, json_schema_extra.values, strict=False):
                key = string_constant(key_node)
                if key == "update_only":
                    update_only = bool_constant(value_node)
                elif key == "runtime_only":
                    runtime_only = bool_constant(value_node)

        if update_only is None and runtime_only is None:
            return
        if update_only is True:
            self.update_only_fields.append(field_name)
        if runtime_only is True:
            self.runtime_only_fields.append(field_name)
        if update_only is None and any(
            string_constant(key_node) == "update_only" for key_node in getattr(json_schema_extra, "keys", [])
        ):
            self.invalid_hash_metadata.append(f"{field_name}.update_only is not boolean")
        if runtime_only is None and any(
            string_constant(key_node) == "runtime_only" for key_node in getattr(json_schema_extra, "keys", [])
        ):
            self.invalid_hash_metadata.append(f"{field_name}.runtime_only is not boolean")
        if update_only is True and runtime_only is True:
            self.invalid_hash_metadata.append(f"{field_name} cannot be both update_only and runtime_only")

    def _analyze_node_method(self, method: ast.FunctionDef) -> None:
        if method.name == "__init__":
            self._analyze_init_method(method)
        elif method.name == "update":
            self._analyze_update_method(method)
        elif method.name == "dependencies":
            self._analyze_dependencies_method(method)
        elif method.name == "get_asset_list":
            self.uses_get_asset_list = True
        elif method.name == "get_table_metadata":
            self.uses_get_table_metadata = True
        elif method.name == "get_column_metadata":
            self.uses_get_column_metadata = True

    def _analyze_init_method(self, method: ast.FunctionDef) -> None:
        for node in ast.walk(method):
            if isinstance(node, ast.Call) and self._is_super_init_call(node):
                if any(keyword.arg == "config" for keyword in node.keywords):
                    self.has_super_init_config = True
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if (
                        isinstance(target, ast.Attribute)
                        and isinstance(target.value, ast.Name)
                        and target.value.id == "self"
                        and isinstance(node.value, ast.Call)
                    ):
                        callee = dotted_name(node.value.func).split(".")[-1]
                        if callee.endswith("Node") or callee == "APIDataNode":
                            self.dependencies_in_init = True

    def _analyze_update_method(self, method: ast.FunctionDef) -> None:
        self.has_update_method = True
        for node in ast.walk(method):
            if isinstance(node, ast.Return):
                if node.value is None or (
                    isinstance(node.value, ast.Constant) and node.value.value is None
                ):
                    self.update_returns_none = True
            if isinstance(node, ast.Call):
                callee = dotted_name(node.func).split(".")[-1]
                if callee == "DataFrame":
                    self.update_calls_dataframe = True
                    self._collect_dataframe_columns(node)
                elif callee == "DatetimeIndex":
                    self._collect_index_name(node)
                elif callee == "set_index":
                    self._collect_set_index_names(node)
                elif callee == "drop_duplicates":
                    self.uses_drop_duplicates = True
                elif callee.endswith("Node") or callee == "APIDataNode":
                    self.dependencies_built_in_update = True
            if isinstance(node, ast.Attribute) and node.attr == "update_statistics":
                self.uses_update_statistics = True
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                text = node.value
                if text == "time_index":
                    self.uses_time_index = True
                if text == "unique_identifier":
                    self.uses_unique_identifier = True
                if text == "asset_symbol":
                    self.uses_asset_symbol = True

    def _analyze_dependencies_method(self, method: ast.FunctionDef) -> None:
        self.has_dependencies_method = True
        for node in ast.walk(method):
            if isinstance(node, ast.Return) and isinstance(node.value, ast.Dict):
                self.dependencies_return_dict = True
                for key_node in node.value.keys:
                    key = string_constant(key_node)
                    if key:
                        self.dependency_keys.append(key)

    def _analyze_global_call(self, node: ast.Call) -> None:
        callee = dotted_name(node.func).split(".")[-1]
        if callee == "RecordDefinition":
            self.uses_record_definition = True
            self._collect_record_definition(node)

    def _collect_dataframe_columns(self, node: ast.Call) -> None:
        data_arg: ast.AST | None = None
        if node.args:
            data_arg = node.args[0]
        data_kw = find_keyword(node, "data")
        if data_kw is not None:
            data_arg = data_kw
        if isinstance(data_arg, ast.Dict):
            for key_node in data_arg.keys:
                key = string_constant(key_node)
                if key is not None:
                    self.column_names.append(key)
        self._collect_index_name(node)

    def _collect_index_name(self, node: ast.Call) -> None:
        name_node = find_keyword(node, "name")
        name = string_constant(name_node)
        if name:
            self.index_names_seen.append(name)
            if name == "time_index":
                self.uses_time_index = True

    def _collect_set_index_names(self, node: ast.Call) -> None:
        if node.args:
            first = node.args[0]
            if isinstance(first, ast.List):
                for elt in first.elts:
                    name = string_constant(elt)
                    if name:
                        self.index_names_seen.append(name)
            else:
                name = string_constant(first)
                if name:
                    self.index_names_seen.append(name)
        for name in self.index_names_seen:
            if name == "time_index":
                self.uses_time_index = True
            if name == "unique_identifier":
                self.uses_unique_identifier = True
            if name == "asset_symbol":
                self.uses_asset_symbol = True

    def _collect_record_definition(self, node: ast.Call) -> None:
        column_name = string_constant(find_keyword(node, "column_name"))
        dtype = string_constant(find_keyword(node, "dtype"))
        if column_name:
            self.column_names.append(column_name)
        if dtype and "datetime64" in dtype:
            self.uses_datetime_payload_column = True

    def _finalize_columns(self) -> None:
        unique_columns = []
        seen = set()
        for column in self.column_names:
            if column not in seen:
                seen.add(column)
                unique_columns.append(column)
        self.column_names = unique_columns
        self.column_names_too_long = [name for name in self.column_names if len(name) > 63]
        self.uppercase_column_names = [
            name for name in self.column_names if not isinstance(name, str) or name != name.lower()
        ]

    @staticmethod
    def _is_super_init_call(node: ast.Call) -> bool:
        func = node.func
        return (
            isinstance(func, ast.Attribute)
            and func.attr == "__init__"
            and isinstance(func.value, ast.Call)
            and isinstance(func.value.func, ast.Name)
            and func.value.func.id == "super"
        )


class SimpleTableResponseAnalyzer:
    def __init__(self, response_text: str):
        self.response_text = response_text
        self.lowered = response_text.lower()
        self.python_blocks = extract_python_blocks(response_text)
        self.code_text = "\n\n".join(self.python_blocks)
        self.parse_errors: list[str] = []
        self.trees: list[ast.AST] = []

        self.simple_table_classes: list[str] = []
        self.simple_table_updater_classes: list[str] = []
        self.config_classes: list[str] = []
        self.schema_class_names: set[str] = set()
        self.updater_schema_names: list[str] = []

        self.user_declared_id_tables: list[str] = []
        self.field_names: list[str] = []
        self.column_names_too_long: list[str] = []
        self.physical_column_names_too_long: list[str] = []
        self.duplicate_metadata_errors: list[str] = []
        self.foreign_key_targets: list[str] = []
        self.invalid_on_delete: list[str] = []
        self.filter_disabled_fields: set[str] = set()
        self.order_enabled_fields: set[str] = set()
        self.order_disabled_fields: set[str] = set()
        self.indexed_fields: set[str] = set()
        self.unique_indexed_fields: set[str] = set()

        self.dependencies_returned = False
        self.dependency_keys: set[str] = set()
        self.dependency_values_look_like_updaters = True
        self.dependencies_built_in_update = False
        self.uses_execute_filter = False
        self.uses_request_directly = False
        self.uses_get_data_from_filter_directly = False

        self.uses_removed_legacy_patterns = False
        self.invalid_hash_metadata: list[str] = []
        self.update_only_fields: list[str] = []
        self.runtime_only_fields: list[str] = []

        self.has_update_method = False
        self.update_returns_none = False
        self.update_returns_overwrite_true = False
        self.update_returns_raw_dicts = False
        self.update_returns_dataframe = False
        self.update_returns_schema_instances = False
        self.update_mentions_backend_ids = False
        self.uses_insert_records = False
        self.uses_upsert_records = False
        self.uses_delete = False
        self.uses_id_filtering = False
        self.uses_filters_namespace = False
        self.uses_order_key = False
        self.uses_node_unique_identifier = False
        self.uses_join = False
        self.join_non_join_types = False
        self.uses_storage_hash = False
        self.mentions_backend_id = False
        self.mentions_business_key = False
        self.mentions_insert_without_id = False
        self.mentions_read_back_ids = False
        self.mentions_overwrite_requires_id = False
        self.mentions_simpletable_vs_datanode = False
        self.mentions_row_oriented = False
        self.mentions_time_series = False
        self.mentions_full_orm = False

        self._parse()
        self._scan_text()
        self._analyze_trees()

    def _parse(self) -> None:
        for index, block in enumerate(self.python_blocks, start=1):
            try:
                self.trees.append(ast.parse(block))
            except SyntaxError as exc:
                self.parse_errors.append(f"python block {index}: {exc.msg} line {exc.lineno}")

    def _scan_text(self) -> None:
        lowered = self.lowered
        self.uses_removed_legacy_patterns = contains_any(
            lowered,
            ["_args_ignore_in_storage_hash", "init_meta", "ignore_from_storage_hash"],
        )
        self.uses_execute_filter = "execute_filter(" in self.code_text or "execute_filter" in lowered
        self.uses_request_directly = ".request(" in self.code_text
        self.uses_get_data_from_filter_directly = "get_data_from_filter" in self.code_text or "get_data_from_filter" in lowered
        self.uses_insert_records = "insert_records(" in self.code_text or "insert_records" in lowered
        self.uses_upsert_records = "upsert_records(" in self.code_text or "upsert_records" in lowered
        self.uses_delete = ".delete(" in self.code_text or " delete(" in self.code_text or "delete(" in lowered
        self.uses_filters_namespace = ".filters." in self.code_text or ".filters." in lowered
        self.uses_id_filtering = ".filters.id." in self.code_text or ".filters.id." in lowered
        self.uses_order_key = "order_key(" in self.code_text or "order_key" in lowered
        self.uses_node_unique_identifier = "node_unique_identifier" in lowered
        self.uses_join = ".join(" in self.code_text or "joins=" in self.code_text or " join " in lowered
        self.uses_storage_hash = "storage_hash" in lowered
        self.mentions_backend_id = contains_any(lowered, ["backend id", "backend-managed id", "row id", "returned id"])
        self.mentions_business_key = contains_any(lowered, ["business key", "customer_code", "external_id", "lookup key"])
        self.mentions_insert_without_id = contains_any(lowered, ["insert without id", "omit id", "without ids", "without id"])
        self.mentions_read_back_ids = contains_any(lowered, ["read back ids", "read rows back", "recover backend ids", "map customer_code -> id", "map external_id -> id"])
        self.mentions_overwrite_requires_id = contains_any(lowered, ["overwrite requires id", "upsert requires id", "overwrite/upsert", "overwrite is keyed by backend id"])
        self.mentions_simpletable_vs_datanode = "datanode" in lowered and "simpletable" in lowered
        self.mentions_row_oriented = "row-oriented" in lowered or "row oriented" in lowered
        self.mentions_time_series = "time series" in lowered or "time-series" in lowered
        self.mentions_full_orm = "full orm" in lowered or "full database layer" in lowered
        self.update_mentions_backend_ids = contains_any(
            lowered,
            ["records should already include backend ids", "rows already include backend ids", "returned rows include backend ids"],
        )

    def _analyze_trees(self) -> None:
        for tree in self.trees:
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    self._analyze_class(node)

    def _analyze_class(self, node: ast.ClassDef) -> None:
        base_names = {dotted_name(base).split(".")[-1] for base in node.bases}
        is_table = "SimpleTable" in base_names
        is_updater = "SimpleTableUpdater" in base_names
        is_config = bool(base_names & {"SimpleTableUpdaterConfiguration", "BaseConfiguration"})

        if is_table:
            self.simple_table_classes.append(node.name)
            self.schema_class_names.add(node.name)
            for stmt in node.body:
                self._analyze_simple_table_stmt(node.name, stmt)
        if is_updater:
            self.simple_table_updater_classes.append(node.name)
            for stmt in node.body:
                self._analyze_updater_stmt(stmt)
        if is_config:
            self.config_classes.append(node.name)
            for stmt in node.body:
                self._analyze_config_stmt(stmt)

    def _analyze_simple_table_stmt(self, class_name: str, stmt: ast.stmt) -> None:
        if not isinstance(stmt, ast.AnnAssign) or not isinstance(stmt.target, ast.Name):
            return
        field_name = stmt.target.id
        if field_name == "id":
            self.user_declared_id_tables.append(class_name)
            return

        self.field_names.append(field_name)
        if len(field_name) > 63:
            self.column_names_too_long.append(field_name)

        metadata = self._extract_annotated_metadata(stmt.annotation)
        metadata_counts = {"ForeignKey": 0, "Index": 0, "Ops": 0}
        field_has_foreign_key = False
        for meta in metadata:
            call_name = dotted_name(meta.func).split(".")[-1] if isinstance(meta, ast.Call) else ""
            if call_name in metadata_counts:
                metadata_counts[call_name] += 1
            if call_name == "ForeignKey" and isinstance(meta, ast.Call):
                field_has_foreign_key = True
                target = None
                if meta.args:
                    target = string_constant(meta.args[0])
                target = target or string_constant(find_keyword(meta, "target"))
                if target:
                    self.foreign_key_targets.append(target)
                on_delete = None
                if len(meta.args) >= 2:
                    on_delete = string_constant(meta.args[1])
                on_delete = on_delete or string_constant(find_keyword(meta, "on_delete"))
                if on_delete is not None and on_delete not in {"cascade", "restrict", "set_null"}:
                    self.invalid_on_delete.append(f"{field_name}.on_delete={on_delete}")
            elif call_name == "Index" and isinstance(meta, ast.Call):
                self.indexed_fields.add(field_name)
                unique = None
                if meta.args:
                    unique = bool_constant(meta.args[0])
                unique = unique if unique is not None else bool_constant(find_keyword(meta, "unique"))
                if unique:
                    self.unique_indexed_fields.add(field_name)
            elif call_name == "Ops" and isinstance(meta, ast.Call):
                filter_value = None
                order_value = None
                if meta.args:
                    filter_value = bool_constant(meta.args[0])
                filter_value = filter_value if filter_value is not None else bool_constant(find_keyword(meta, "filter"))
                if len(meta.args) >= 4:
                    order_value = bool_constant(meta.args[3])
                order_value = order_value if order_value is not None else bool_constant(find_keyword(meta, "order"))
                if filter_value is False:
                    self.filter_disabled_fields.add(field_name)
                if order_value is True:
                    self.order_enabled_fields.add(field_name)
                if order_value is False:
                    self.order_disabled_fields.add(field_name)

        for kind, count in metadata_counts.items():
            if count > 1:
                self.duplicate_metadata_errors.append(
                    f"{class_name}.{field_name} declares multiple {kind} metadata entries."
                )

        if field_has_foreign_key:
            physical_name = f"{field_name}_id"
            if len(physical_name) > 63:
                self.physical_column_names_too_long.append(physical_name)

    def _analyze_updater_stmt(self, stmt: ast.stmt) -> None:
        if isinstance(stmt, ast.Assign):
            for target in stmt.targets:
                if isinstance(target, ast.Name) and target.id == "SIMPLE_TABLE_SCHEMA":
                    schema_name = dotted_name(stmt.value)
                    if schema_name:
                        self.updater_schema_names.append(schema_name.split(".")[-1])
        if isinstance(stmt, ast.FunctionDef):
            if stmt.name == "dependencies":
                self._analyze_dependencies_method(stmt)
            elif stmt.name == "update":
                self._analyze_update_method(stmt)

    def _analyze_dependencies_method(self, method: ast.FunctionDef) -> None:
        for node in ast.walk(method):
            if isinstance(node, ast.Return) and isinstance(node.value, ast.Dict):
                self.dependencies_returned = True
                for key_node, value_node in zip(node.value.keys, node.value.values, strict=False):
                    key = string_constant(key_node)
                    if key:
                        self.dependency_keys.add(key)
                    if isinstance(value_node, ast.Call):
                        callee = dotted_name(value_node.func).split(".")[-1]
                        if not callee.endswith("Updater"):
                            self.dependency_values_look_like_updaters = False
                    elif isinstance(value_node, ast.Attribute):
                        continue
                    elif isinstance(value_node, ast.Name):
                        continue
                    else:
                        self.dependency_values_look_like_updaters = False

    def _analyze_update_method(self, method: ast.FunctionDef) -> None:
        self.has_update_method = True
        for node in ast.walk(method):
            if isinstance(node, ast.Return):
                if node.value is None or (
                    isinstance(node.value, ast.Constant) and node.value.value is None
                ):
                    self.update_returns_none = True
                elif isinstance(node.value, ast.Tuple) and len(node.value.elts) == 2:
                    overwrite_value = bool_constant(node.value.elts[1])
                    if overwrite_value is True:
                        self.update_returns_overwrite_true = True
                    self._inspect_update_return_payload(node.value.elts[0])
                else:
                    self._inspect_update_return_payload(node.value)
            elif isinstance(node, ast.Call):
                callee = dotted_name(node.func).split(".")[-1]
                if callee == "DataFrame":
                    self.update_returns_dataframe = True
                elif callee == "execute_filter":
                    self.uses_execute_filter = True
                elif callee == "request":
                    self.uses_request_directly = True
                elif callee == "get_data_from_filter":
                    self.uses_get_data_from_filter_directly = True
                elif callee.endswith("Updater"):
                    self.dependencies_built_in_update = True

    def _inspect_update_return_payload(self, node: ast.AST) -> None:
        if isinstance(node, ast.List):
            if all(isinstance(elt, ast.Dict) for elt in node.elts) and node.elts:
                self.update_returns_raw_dicts = True
            for elt in node.elts:
                if isinstance(elt, ast.Call):
                    callee = dotted_name(elt.func).split(".")[-1]
                    if callee in self.schema_class_names or callee in self.updater_schema_names:
                        self.update_returns_schema_instances = True
                    if callee == "dict":
                        self.update_returns_raw_dicts = True
                elif isinstance(elt, ast.Dict):
                    self.update_returns_raw_dicts = True
        elif isinstance(node, ast.Call):
            callee = dotted_name(node.func).split(".")[-1]
            if callee in self.schema_class_names or callee in self.updater_schema_names:
                self.update_returns_schema_instances = True
            elif callee == "DataFrame":
                self.update_returns_dataframe = True
            elif callee == "dict":
                self.update_returns_raw_dicts = True
        elif isinstance(node, ast.Name):
            return

    def _analyze_config_stmt(self, stmt: ast.stmt) -> None:
        if not isinstance(stmt, ast.AnnAssign):
            return
        if not isinstance(stmt.target, ast.Name):
            return
        field_name = stmt.target.id
        call = stmt.value
        if not isinstance(call, ast.Call):
            return
        if dotted_name(call.func).split(".")[-1] != "Field":
            return

        json_schema_extra = find_keyword(call, "json_schema_extra")
        update_only = None
        runtime_only = None
        if isinstance(json_schema_extra, ast.Dict):
            for key_node, value_node in zip(json_schema_extra.keys, json_schema_extra.values, strict=False):
                key = string_constant(key_node)
                if key == "update_only":
                    update_only = bool_constant(value_node)
                elif key == "runtime_only":
                    runtime_only = bool_constant(value_node)

        if update_only is None and runtime_only is None:
            return
        if update_only is True:
            self.update_only_fields.append(field_name)
        if runtime_only is True:
            self.runtime_only_fields.append(field_name)
        if update_only is None and any(
            string_constant(key_node) == "update_only" for key_node in getattr(json_schema_extra, "keys", [])
        ):
            self.invalid_hash_metadata.append(f"{field_name}.update_only is not boolean")
        if runtime_only is None and any(
            string_constant(key_node) == "runtime_only" for key_node in getattr(json_schema_extra, "keys", [])
        ):
            self.invalid_hash_metadata.append(f"{field_name}.runtime_only is not boolean")
        if update_only is True and runtime_only is True:
            self.invalid_hash_metadata.append(f"{field_name} cannot be both update_only and runtime_only")

    @staticmethod
    def _extract_annotated_metadata(annotation: ast.AST | None) -> list[ast.AST]:
        if not isinstance(annotation, ast.Subscript):
            return []
        if dotted_name(annotation.value).split(".")[-1] != "Annotated":
            return []
        slice_value = annotation.slice
        if isinstance(slice_value, ast.Tuple):
            return list(slice_value.elts[1:])
        return []


def build_weighted_quality_check(
    weights: dict[str, float], check_id: str, score: float, notes: list[str]
) -> dict:
    weight = weights[check_id]
    bounded = round(max(0.0, min(score, 1.0)), 4)
    return {
        "id": check_id,
        "weight": weight,
        "score": bounded,
        "weighted_score": round(bounded * weight, 4),
        "notes": notes,
    }


def score_or_001(response_text: str, rubric: dict) -> dict:
    lowered = response_text.lower()
    results: list[dict] = []

    def add_result(criterion_id: str, score: float, evidence: list[str]) -> None:
        weight = next(
            item["weight"]
            for item in rubric["criteria"]
            if item["id"] == criterion_id
        )
        results.append(
            {
                "id": criterion_id,
                "weight": weight,
                "score": score,
                "weighted_score": round(score * weight, 4),
                "evidence": evidence,
            }
        )

    workflow_evidence = []
    workflow_score = 0.0
    if "scheduled_jobs.yaml" in lowered:
        workflow_score = 0.5
        workflow_evidence.append("mentions scheduled_jobs.yaml")
    if contains_any(lowered, ["schedule_batch_jobs", "repository-managed", "version control", "team-managed"]):
        workflow_score = 1.0
        workflow_evidence.append("treats recurring workflow as code-managed")
    add_result("workflow-choice", workflow_score, workflow_evidence)

    artifact_evidence = []
    artifact_score = 0.0
    if "artifact" in lowered:
        artifact_score = 0.5
        artifact_evidence.append("mentions Artifact")
    if contains_any(lowered, ["platform-managed file", "file primitive", "local path", "fragile local path"]):
        artifact_score = 1.0
        artifact_evidence.append("explains why Artifact is used instead of local files")
    add_result("artifact-handling", artifact_score, artifact_evidence)

    pinned_image_evidence = []
    pinned_image_score = 0.0
    if contains_any(lowered, ["project image", "related_image_id", "pinned image"]):
        pinned_image_score = 0.5
        pinned_image_evidence.append("mentions project image pinning")
    if contains_any(lowered, ["related_image_id", "pinned image", "freeze", "reproducible"]):
        pinned_image_score = 1.0
        pinned_image_evidence.append("ties reproducibility to image pinning")
    add_result("pinned-image", pinned_image_score, pinned_image_evidence)

    strict_evidence = []
    strict_score = 0.0
    if "--strict" in response_text:
        strict_score = 0.5
        strict_evidence.append("mentions --strict")
    if "--strict" in response_text and contains_any(
        lowered,
        ["not the default", "do not use", "only if", "full desired state", "dangerous", "casually"],
    ):
        strict_score = 1.0
        strict_evidence.append("treats --strict as an intentional/safe choice, not default")
    add_result("strict-safety", strict_score, strict_evidence)

    verification_evidence = []
    verification_score = 0.0
    if contains_any(lowered, ["jobs list", "runs list", "runs logs"]):
        verification_score = 0.5
        verification_evidence.append("mentions post-creation verification commands")
    if contains_all(lowered, ["jobs list", "runs list", "runs logs"]):
        verification_score = 1.0
        verification_evidence.append("covers jobs, runs, and logs verification")
    add_result("verification", verification_score, verification_evidence)

    concrete_evidence = []
    concrete_score = 0.0
    if contains_any(lowered, ["jobs:", "execution_path:", "task_schedule:", "related_image_id:"]):
        concrete_score = 0.5
        concrete_evidence.append("includes YAML-like example")
    if contains_any(lowered, ["mainsequence project schedule_batch_jobs", "mainsequence project sync"]):
        concrete_score = 1.0
        concrete_evidence.append("includes concrete CLI flow")
    add_result("concrete-example", concrete_score, concrete_evidence)

    penalties: list[dict] = []
    penalty_total = 0.0

    invented_command_patterns = [
        "mainsequence project create_image",
        "mainsequence project pin_image",
        "mainsequence project create_job",
        "mainsequence project create_artifact",
        "mainsequence project artifacts list",
        "mainsequence project artifacts show",
    ]
    invented_matches = [pattern for pattern in invented_command_patterns if pattern in lowered]
    if invented_matches:
        penalties.append(
            {
                "id": "invented-cli-commands",
                "amount": 0.25,
                "evidence": invented_matches,
            }
        )
        penalty_total += 0.25

    wrong_yaml_markers = []
    if "mode:" in lowered:
        wrong_yaml_markers.append("mode:")
    if "\n    schedule:" in lowered or "\n    image:" in lowered:
        wrong_yaml_markers.extend(
            marker
            for marker in ["schedule:", "image:"]
            if marker in lowered
        )
    if wrong_yaml_markers and "task_schedule:" not in lowered:
        penalties.append(
            {
                "id": "wrong-job-yaml-shape",
                "amount": 0.2,
                "evidence": wrong_yaml_markers,
            }
        )
        penalty_total += 0.2

    if "related_image_id" not in lowered:
        penalties.append(
            {
                "id": "missing-related-image-id-example",
                "amount": 0.15,
                "evidence": ["response example omitted related_image_id"],
            }
        )
        penalty_total += 0.15

    raw_total = round(sum(item["weighted_score"] for item in results), 4)
    total = round(max(0.0, raw_total - penalty_total), 4)
    return {
        "method": "rule-based-checklist",
        "case_id": "or-001-recurring-artifact-job",
        "raw_score": raw_total,
        "total_score": total,
        "passing_score": rubric["passing_score"],
        "passed": total >= rubric["passing_score"],
        "criteria": results,
        "penalties": penalties,
        "limitations": [
            "This is a heuristic evaluator.",
            "It checks presence of expected concepts but not full reasoning quality.",
        ],
    }


def build_hard_check(check_id: str, passed: bool, notes: list[str]) -> dict:
    return {"id": check_id, "passed": passed, "notes": notes}


def build_quality_check(check_id: str, score: float, notes: list[str]) -> dict:
    weight = DATANODE_QUALITY_WEIGHTS[check_id]
    return {
        "id": check_id,
        "weight": weight,
        "score": round(max(0.0, min(score, 1.0)), 4),
        "weighted_score": round(max(0.0, min(score, 1.0)) * weight, 4),
        "notes": notes,
    }


def score_simpletable_case(case_payload: dict, rubric: dict, response_text: str) -> dict:
    analyzer = SimpleTableResponseAnalyzer(response_text)
    case_id = case_payload["id"]

    hard_fail_checks: list[dict] = []
    findings: list[dict] = []

    schema_notes = []
    schema_passed = True
    if analyzer.simple_table_classes:
        schema_notes.append(f"SimpleTable subclasses: {', '.join(analyzer.simple_table_classes)}")
    else:
        schema_notes.append("No SimpleTable subclass found.")
        schema_passed = False
    if analyzer.user_declared_id_tables:
        schema_notes.append("User-declared id fields: " + ", ".join(sorted(analyzer.user_declared_id_tables)))
        schema_passed = False
    else:
        schema_notes.append("No user-declared id fields detected.")
    if analyzer.column_names_too_long:
        schema_notes.append("Columns longer than 63 chars: " + ", ".join(sorted(analyzer.column_names_too_long)))
        schema_passed = False
    else:
        schema_notes.append("No logical column names over 63 chars detected.")
    if analyzer.physical_column_names_too_long:
        schema_notes.append(
            "Physical FK column names longer than 63 chars: "
            + ", ".join(sorted(analyzer.physical_column_names_too_long))
        )
        schema_passed = False
    else:
        schema_notes.append("No physical foreign-key column names over 63 chars detected.")
    hard_fail_checks.append(build_hard_check("schema-contract", schema_passed, schema_notes))

    metadata_notes = []
    metadata_passed = True
    if analyzer.duplicate_metadata_errors:
        metadata_notes.extend(analyzer.duplicate_metadata_errors)
        metadata_passed = False
    if analyzer.invalid_on_delete:
        metadata_notes.extend(analyzer.invalid_on_delete)
        metadata_passed = False
    if analyzer.foreign_key_targets:
        metadata_notes.append("Foreign-key targets: " + ", ".join(sorted(set(analyzer.foreign_key_targets))))
    if not metadata_notes:
        metadata_notes.append("No field metadata violations detected.")
    hard_fail_checks.append(build_hard_check("field-metadata-contract", metadata_passed, metadata_notes))

    filter_notes = []
    filter_passed = True
    if analyzer.uses_node_unique_identifier:
        filter_notes.append("Simple-table join/request uses node_unique_identifier.")
        filter_passed = False
    else:
        filter_notes.append("No node_unique_identifier usage detected.")
    if analyzer.uses_order_key and not analyzer.order_enabled_fields and analyzer.field_names:
        filter_notes.append("Uses order_key() without explicit Ops(order=True) evidence.")
        filter_passed = False
    else:
        filter_notes.append("No orderability violation detected.")
    hard_fail_checks.append(build_hard_check("filter-and-join-contract", filter_passed, filter_notes))

    for check in hard_fail_checks:
        if not check["passed"]:
            findings.append(
                {
                    "severity": "hard_fail",
                    "message": f"{check['id']} failed.",
                    "notes": check["notes"],
                }
            )

    quality_checks: list[dict] = []

    table_choice_score = 0.0
    table_choice_notes = []
    if analyzer.mentions_row_oriented:
        table_choice_score += 0.4
        table_choice_notes.append("Recognizes row-oriented shape.")
    if analyzer.mentions_simpletable_vs_datanode or analyzer.mentions_time_series:
        table_choice_score += 0.35
        table_choice_notes.append("Distinguishes SimpleTable from DataNode / time-series usage.")
    if analyzer.mentions_full_orm:
        table_choice_score += 0.25
        table_choice_notes.append("Recognizes SimpleTable is not a full ORM/database layer.")
    quality_checks.append(
        build_weighted_quality_check(
            SIMPLETABLE_QUALITY_WEIGHTS,
            "table-choice-and-scope",
            table_choice_score,
            table_choice_notes or ["No explicit table-choice evidence found."],
        )
    )

    schema_design_score = 0.0
    schema_design_notes = []
    if analyzer.field_names:
        schema_design_score += 0.25
        schema_design_notes.append("Defines schema fields explicitly.")
    if analyzer.indexed_fields:
        schema_design_score += 0.2
        schema_design_notes.append("Uses Index metadata.")
    if analyzer.unique_indexed_fields:
        schema_design_score += 0.15
        schema_design_notes.append("Uses unique index metadata.")
    if analyzer.order_enabled_fields or analyzer.uses_filters_namespace:
        schema_design_score += 0.2
        schema_design_notes.append("Uses Ops/filter/order schema surface.")
    if analyzer.mentions_business_key:
        schema_design_score += 0.2
        schema_design_notes.append("Discusses business-key design.")
    quality_checks.append(
        build_weighted_quality_check(
            SIMPLETABLE_QUALITY_WEIGHTS,
            "schema-design-quality",
            schema_design_score,
            schema_design_notes or ["No schema-design-quality evidence found."],
        )
    )

    id_workflow_score = 0.0
    id_workflow_notes = []
    if analyzer.mentions_insert_without_id:
        id_workflow_score += 0.3
        id_workflow_notes.append("Explains insert without id.")
    if analyzer.mentions_read_back_ids or analyzer.uses_id_filtering:
        id_workflow_score += 0.35
        id_workflow_notes.append("Explains reading back ids or filtering by id.")
    if analyzer.mentions_overwrite_requires_id:
        id_workflow_score += 0.35
        id_workflow_notes.append("Explains overwrite/upsert requires backend ids.")
    quality_checks.append(
        build_weighted_quality_check(
            SIMPLETABLE_QUALITY_WEIGHTS,
            "id-mutation-workflow",
            id_workflow_score,
            id_workflow_notes or ["No id lifecycle evidence found."],
        )
    )

    fk_quality_score = 0.0
    fk_quality_notes = []
    if analyzer.foreign_key_targets:
        fk_quality_score += 0.4
        fk_quality_notes.append("Declares foreign-key targets.")
    if analyzer.dependency_keys:
        fk_quality_score += 0.3
        fk_quality_notes.append("Shows dependency keys: " + ", ".join(sorted(analyzer.dependency_keys)))
    if analyzer.mentions_read_back_ids:
        fk_quality_score += 0.3
        fk_quality_notes.append("Uses returned ids for parent-child workflow.")
    quality_checks.append(
        build_weighted_quality_check(
            SIMPLETABLE_QUALITY_WEIGHTS,
            "foreign-key-workflow-quality",
            fk_quality_score,
            fk_quality_notes or ["No foreign-key workflow evidence found."],
        )
    )

    updater_design_score = 0.0
    updater_design_notes = []
    if analyzer.simple_table_updater_classes:
        updater_design_score += 0.4
        updater_design_notes.append("Defines SimpleTableUpdater subclass.")
    if analyzer.dependencies_returned:
        updater_design_score += 0.3
        updater_design_notes.append("dependencies() returns a map.")
    if not analyzer.dependencies_built_in_update:
        updater_design_score += 0.15
        updater_design_notes.append("No dependency construction in update().")
    if analyzer.config_classes:
        updater_design_score += 0.15
        updater_design_notes.append("Uses updater configuration class.")
    if (
        not analyzer.simple_table_updater_classes
        and not analyzer.dependencies_returned
        and not analyzer.config_classes
    ):
        updater_design_score = 1.0
        updater_design_notes = ["Schema-focused response; updater-design check treated as not applicable."]
    quality_checks.append(
        build_weighted_quality_check(
            SIMPLETABLE_QUALITY_WEIGHTS,
            "updater-design",
            updater_design_score,
            updater_design_notes or ["No updater-design evidence found."],
        )
    )

    filter_design_score = 0.0
    filter_design_notes = []
    if analyzer.uses_filters_namespace:
        filter_design_score += 0.35
        filter_design_notes.append("Builds filters from schema surface.")
    if analyzer.uses_execute_filter:
        filter_design_score += 0.35
        filter_design_notes.append("Executes filters through updater.")
    if analyzer.uses_join:
        filter_design_score += 0.15
        filter_design_notes.append("Includes join/filter workflow.")
    if analyzer.uses_order_key:
        filter_design_score += 0.15
        filter_design_notes.append("Uses validated ordering surface.")
    quality_checks.append(
        build_weighted_quality_check(
            SIMPLETABLE_QUALITY_WEIGHTS,
            "filtering-and-join-design",
            filter_design_score,
            filter_design_notes or ["No filtering/join design evidence found."],
        )
    )

    operational_score = 0.0
    operational_notes = []
    if analyzer.uses_insert_records:
        operational_score += 0.25
        operational_notes.append("Shows insert workflow.")
    if analyzer.uses_execute_filter:
        operational_score += 0.25
        operational_notes.append("Shows query workflow.")
    if analyzer.uses_upsert_records or analyzer.mentions_overwrite_requires_id:
        operational_score += 0.25
        operational_notes.append("Shows overwrite/upsert workflow.")
    if analyzer.uses_delete:
        operational_score += 0.25
        operational_notes.append("Shows delete workflow.")
    if (
        not analyzer.uses_insert_records
        and not analyzer.uses_execute_filter
        and not analyzer.uses_upsert_records
        and not analyzer.uses_delete
    ):
        operational_score = 1.0
        operational_notes = ["Schema-focused response; operational workflow check treated as not applicable."]
    quality_checks.append(
        build_weighted_quality_check(
            SIMPLETABLE_QUALITY_WEIGHTS,
            "operational-clarity",
            operational_score,
            operational_notes or ["No operational workflow evidence found."],
        )
    )

    for item in quality_checks:
        if item["score"] < 0.5:
            findings.append(
                {
                    "severity": "major_quality_issue" if item["score"] < 0.25 else "minor_quality_issue",
                    "message": f"{item['id']} scored {item['score']:.2f}.",
                    "notes": item["notes"],
                }
            )

    hard_fail_passed = all(check["passed"] for check in hard_fail_checks)
    raw_total = round(sum(item["weighted_score"] for item in quality_checks), 4)
    passing_score = float(rubric.get("passing_score", 0.85))
    passed = hard_fail_passed and raw_total >= passing_score

    limitations = [
        "This is a heuristic evaluator based on response text and Python code blocks.",
        "It cannot prove real backend mutation behavior without execution.",
        "Some SimpleTable constraints are inferred from code shape rather than runtime execution.",
    ]
    if analyzer.parse_errors:
        limitations.append("Some Python code blocks could not be parsed: " + "; ".join(analyzer.parse_errors))

    return {
        "method": "rule-based-checklist",
        "case_id": case_id,
        "raw_score": raw_total,
        "total_score": raw_total,
        "passing_score": passing_score,
        "passed": passed,
        "hard_fail_passed": hard_fail_passed,
        "hard_fail_checks": hard_fail_checks,
        "quality_checks": quality_checks,
        "findings": findings,
        "limitations": limitations,
    }


def score_simpletable_updater_case(case_payload: dict, rubric: dict, response_text: str) -> dict:
    analyzer = SimpleTableResponseAnalyzer(response_text)
    case_id = case_payload["id"]

    hard_fail_checks: list[dict] = []
    findings: list[dict] = []

    ownership_notes = []
    ownership_passed = True
    if analyzer.simple_table_updater_classes:
        ownership_notes.append(
            "SimpleTableUpdater subclasses: " + ", ".join(analyzer.simple_table_updater_classes)
        )
    else:
        ownership_notes.append("No SimpleTableUpdater subclass found.")
        ownership_passed = False
    if analyzer.updater_schema_names:
        ownership_notes.append("SIMPLE_TABLE_SCHEMA targets: " + ", ".join(sorted(set(analyzer.updater_schema_names))))
    else:
        ownership_notes.append("No SIMPLE_TABLE_SCHEMA assignment found.")
        ownership_passed = False
    hard_fail_checks.append(build_hard_check("updater-type-and-schema-ownership", ownership_passed, ownership_notes))

    config_notes = []
    config_passed = True
    if analyzer.config_classes:
        config_notes.append("Config classes: " + ", ".join(sorted(set(analyzer.config_classes))))
    else:
        config_notes.append("No updater configuration class found.")
        config_passed = False
    if analyzer.uses_removed_legacy_patterns:
        config_notes.append("Uses removed legacy hashing patterns.")
        config_passed = False
    if analyzer.invalid_hash_metadata:
        config_notes.extend(analyzer.invalid_hash_metadata)
        config_passed = False
    if analyzer.update_only_fields:
        config_notes.append("update_only fields: " + ", ".join(sorted(analyzer.update_only_fields)))
    if analyzer.runtime_only_fields:
        config_notes.append("runtime_only fields: " + ", ".join(sorted(analyzer.runtime_only_fields)))
    hard_fail_checks.append(build_hard_check("configuration-and-hash-contract", config_passed, config_notes))

    dependency_notes = []
    dependency_passed = True
    if analyzer.foreign_key_targets:
        dependency_notes.append("Foreign-key targets: " + ", ".join(sorted(set(analyzer.foreign_key_targets))))
        missing_targets = sorted(set(analyzer.foreign_key_targets) - analyzer.dependency_keys)
        if missing_targets:
            dependency_notes.append("Foreign-key targets missing from dependencies(): " + ", ".join(missing_targets))
            dependency_passed = False
    else:
        dependency_notes.append("No foreign-key targets detected.")
    if analyzer.dependency_keys:
        dependency_notes.append("Dependency keys: " + ", ".join(sorted(analyzer.dependency_keys)))
    else:
        dependency_notes.append("No dependencies() mapping detected.")
        if analyzer.foreign_key_targets:
            dependency_passed = False
    if not analyzer.dependency_values_look_like_updaters:
        dependency_notes.append("Some dependency values do not look like SimpleTableUpdater instances.")
        dependency_passed = False
    hard_fail_checks.append(build_hard_check("foreign-key-dependency-resolution-contract", dependency_passed, dependency_notes))

    update_notes = []
    update_passed = True
    if analyzer.has_update_method:
        update_notes.append("Found update() method.")
    else:
        update_notes.append("No update() method found.")
        update_passed = False
    if analyzer.update_returns_none:
        update_notes.append("update() returns None.")
        update_passed = False
    if analyzer.update_returns_dataframe:
        update_notes.append("update() returns/constructs a DataFrame.")
        update_passed = False
    if analyzer.update_returns_raw_dicts:
        update_notes.append("update() returns raw dict payloads.")
        update_passed = False
    if analyzer.update_returns_schema_instances:
        update_notes.append("update() returns schema instances.")
    elif analyzer.has_update_method:
        update_notes.append("No explicit schema-instance return detected.")
    hard_fail_checks.append(build_hard_check("update-return-contract", update_passed, update_notes))

    mutation_notes = []
    mutation_passed = True
    if analyzer.update_returns_overwrite_true:
        mutation_notes.append("update() returns overwrite=True.")
        if not (
            analyzer.mentions_overwrite_requires_id
            or analyzer.update_mentions_backend_ids
            or analyzer.uses_id_filtering
            or analyzer.mentions_read_back_ids
        ):
            mutation_notes.append("Overwrite is proposed without backend-id evidence.")
            mutation_passed = False
    else:
        mutation_notes.append("No overwrite=True return detected.")
    if analyzer.mentions_business_key and analyzer.update_returns_overwrite_true and not analyzer.mentions_read_back_ids:
        mutation_notes.append("Business-key overwrite path lacks id-resolution evidence.")
        mutation_passed = False
    if analyzer.uses_delete and not (analyzer.mentions_backend_id or analyzer.uses_id_filtering):
        mutation_notes.append("Delete is mentioned without explicit id evidence.")
        mutation_passed = False
    hard_fail_checks.append(build_hard_check("mutation-semantics-contract", mutation_passed, mutation_notes))

    filter_notes = []
    filter_passed = True
    if analyzer.uses_request_directly and not analyzer.uses_execute_filter:
        filter_notes.append("Uses low-level request() path without execute_filter().")
        filter_passed = False
    else:
        filter_notes.append("No filter execution bypass detected.")
    if analyzer.uses_get_data_from_filter_directly:
        filter_notes.append("Uses get_data_from_filter directly.")
        filter_passed = False
    if analyzer.uses_node_unique_identifier:
        filter_notes.append("Uses node_unique_identifier in simple-table workflow.")
        filter_passed = False
    if analyzer.uses_order_key and not analyzer.order_enabled_fields and analyzer.field_names:
        filter_notes.append("Uses order_key() without explicit Ops(order=True) evidence.")
        filter_passed = False
    hard_fail_checks.append(build_hard_check("filter-execution-contract", filter_passed, filter_notes))

    for check in hard_fail_checks:
        if not check["passed"]:
            findings.append(
                {
                    "severity": "hard_fail",
                    "message": f"{check['id']} failed.",
                    "notes": check["notes"],
                }
            )

    quality_checks: list[dict] = []

    responsibility_score = 0.0
    responsibility_notes = []
    if analyzer.simple_table_updater_classes:
        responsibility_score += 0.4
        responsibility_notes.append("Defines updater ownership clearly.")
    if analyzer.updater_schema_names:
        responsibility_score += 0.2
        responsibility_notes.append("Connects updater to schema.")
    if analyzer.uses_insert_records or analyzer.uses_execute_filter or analyzer.uses_upsert_records:
        responsibility_score += 0.4
        responsibility_notes.append("Covers real updater workflow rather than schema only.")
    quality_checks.append(
        build_weighted_quality_check(
            SIMPLETABLE_UPDATER_QUALITY_WEIGHTS,
            "updater-responsibility-clarity",
            responsibility_score,
            responsibility_notes or ["No updater responsibility evidence found."],
        )
    )

    dep_score = 0.0
    dep_notes = []
    if analyzer.dependencies_returned:
        dep_score += 0.45
        dep_notes.append("dependencies() returns a map.")
    if analyzer.dependency_keys:
        dep_score += 0.25
        dep_notes.append("Dependency keys: " + ", ".join(sorted(analyzer.dependency_keys)))
    if analyzer.dependency_values_look_like_updaters:
        dep_score += 0.15
        dep_notes.append("Dependency values look like updater references.")
    if not analyzer.dependencies_built_in_update:
        dep_score += 0.15
        dep_notes.append("No ad hoc dependency construction in update().")
    quality_checks.append(
        build_weighted_quality_check(
            SIMPLETABLE_UPDATER_QUALITY_WEIGHTS,
            "dependency-design",
            dep_score,
            dep_notes or ["No dependency-design evidence found."],
        )
    )

    fk_score = 0.0
    fk_notes = []
    if analyzer.foreign_key_targets:
        fk_score += 0.35
        fk_notes.append("Declares foreign-key targets.")
    if analyzer.mentions_read_back_ids:
        fk_score += 0.35
        fk_notes.append("Reads back parent ids before building children.")
    if analyzer.dependency_keys:
        fk_score += 0.15
        fk_notes.append("Uses dependency-key based FK model.")
    if not analyzer.invalid_on_delete:
        fk_score += 0.15
        fk_notes.append("No invalid on_delete metadata detected.")
    quality_checks.append(
        build_weighted_quality_check(
            SIMPLETABLE_UPDATER_QUALITY_WEIGHTS,
            "foreign-key-workflow-quality",
            fk_score,
            fk_notes or ["No foreign-key workflow evidence found."],
        )
    )

    overwrite_score = 0.0
    overwrite_notes = []
    if analyzer.mentions_insert_without_id:
        overwrite_score += 0.25
        overwrite_notes.append("Explains insert-only default.")
    if analyzer.mentions_overwrite_requires_id:
        overwrite_score += 0.35
        overwrite_notes.append("Explains overwrite requires backend ids.")
    if analyzer.mentions_business_key:
        overwrite_score += 0.15
        overwrite_notes.append("Distinguishes business key from mutation key.")
    if analyzer.mentions_read_back_ids:
        overwrite_score += 0.25
        overwrite_notes.append("Explains id recovery before overwrite.")
    quality_checks.append(
        build_weighted_quality_check(
            SIMPLETABLE_UPDATER_QUALITY_WEIGHTS,
            "insert-vs-overwrite-judgment",
            overwrite_score,
            overwrite_notes or ["No insert-vs-overwrite evidence found."],
        )
    )

    lifecycle_score = 0.0
    lifecycle_notes = []
    if analyzer.mentions_insert_without_id:
        lifecycle_score += 0.3
        lifecycle_notes.append("Insert stage explained.")
    if analyzer.mentions_read_back_ids or analyzer.uses_id_filtering:
        lifecycle_score += 0.35
        lifecycle_notes.append("Id recovery/read-back stage explained.")
    if analyzer.uses_upsert_records or analyzer.uses_delete or analyzer.mentions_overwrite_requires_id:
        lifecycle_score += 0.35
        lifecycle_notes.append("Later mutation stage explained.")
    quality_checks.append(
        build_weighted_quality_check(
            SIMPLETABLE_UPDATER_QUALITY_WEIGHTS,
            "id-lifecycle-clarity",
            lifecycle_score,
            lifecycle_notes or ["No id lifecycle evidence found."],
        )
    )

    filter_workflow_score = 0.0
    filter_workflow_notes = []
    if analyzer.uses_filters_namespace:
        filter_workflow_score += 0.35
        filter_workflow_notes.append("Builds filters from typed schema.")
    if analyzer.uses_execute_filter:
        filter_workflow_score += 0.35
        filter_workflow_notes.append("Executes filters through updater.")
    if analyzer.uses_join:
        filter_workflow_score += 0.15
        filter_workflow_notes.append("Includes join workflow.")
    if analyzer.uses_order_key:
        filter_workflow_score += 0.15
        filter_workflow_notes.append("Uses orderable field surface.")
    quality_checks.append(
        build_weighted_quality_check(
            SIMPLETABLE_UPDATER_QUALITY_WEIGHTS,
            "filter-and-join-workflow-quality",
            filter_workflow_score,
            filter_workflow_notes or ["No filter/join workflow evidence found."],
        )
    )

    config_quality_score = 0.0
    config_quality_notes = []
    if analyzer.config_classes:
        config_quality_score += 0.45
        config_quality_notes.append("Uses configuration class.")
    if analyzer.update_only_fields:
        config_quality_score += 0.25
        config_quality_notes.append("Uses update_only classification.")
    if analyzer.runtime_only_fields:
        config_quality_score += 0.2
        config_quality_notes.append("Uses runtime_only classification.")
    if not analyzer.invalid_hash_metadata:
        config_quality_score += 0.1
        config_quality_notes.append("No explicit hash metadata violations detected.")
    quality_checks.append(
        build_weighted_quality_check(
            SIMPLETABLE_UPDATER_QUALITY_WEIGHTS,
            "configuration-quality",
            config_quality_score,
            config_quality_notes or ["No configuration-quality evidence found."],
        )
    )

    operational_score = 0.0
    operational_notes = []
    if analyzer.uses_insert_records:
        operational_score += 0.25
        operational_notes.append("Shows insert path.")
    if analyzer.uses_execute_filter:
        operational_score += 0.25
        operational_notes.append("Shows query path.")
    if analyzer.uses_upsert_records or analyzer.mentions_overwrite_requires_id:
        operational_score += 0.25
        operational_notes.append("Shows overwrite/upsert path.")
    if analyzer.uses_delete:
        operational_score += 0.25
        operational_notes.append("Shows delete path.")
    quality_checks.append(
        build_weighted_quality_check(
            SIMPLETABLE_UPDATER_QUALITY_WEIGHTS,
            "operational-completeness",
            operational_score,
            operational_notes or ["No operational completeness evidence found."],
        )
    )

    for item in quality_checks:
        if item["score"] < 0.5:
            findings.append(
                {
                    "severity": "major_quality_issue" if item["score"] < 0.25 else "minor_quality_issue",
                    "message": f"{item['id']} scored {item['score']:.2f}.",
                    "notes": item["notes"],
                }
            )

    hard_fail_passed = all(check["passed"] for check in hard_fail_checks)
    raw_total = round(sum(item["weighted_score"] for item in quality_checks), 4)
    passing_score = float(rubric.get("passing_score", 0.85))
    passed = hard_fail_passed and raw_total >= passing_score

    limitations = [
        "This is a heuristic evaluator based on response text and Python code blocks.",
        "It cannot prove real backend table resolution or mutation behavior without execution.",
        "Overwrite/id semantics are inferred from the response rather than runtime records.",
    ]
    if analyzer.parse_errors:
        limitations.append("Some Python code blocks could not be parsed: " + "; ".join(analyzer.parse_errors))

    return {
        "method": "rule-based-checklist",
        "case_id": case_id,
        "raw_score": raw_total,
        "total_score": raw_total,
        "passing_score": passing_score,
        "passed": passed,
        "hard_fail_passed": hard_fail_passed,
        "hard_fail_checks": hard_fail_checks,
        "quality_checks": quality_checks,
        "findings": findings,
        "limitations": limitations,
    }


def score_datanode_case(case_payload: dict, rubric: dict, response_text: str) -> dict:
    analyzer = DataNodeResponseAnalyzer(response_text)
    case_id = case_payload["id"]
    tags = set(case_payload.get("tags", []))
    asset_index_required = bool(
        tags
        & {
            "asset-indexed",
            "asset-index",
            "multiindex",
            "assets",
            "unique_identifier",
        }
    )

    hard_fail_checks: list[dict] = []
    findings: list[dict] = []

    constructor_notes = []
    constructor_passed = True
    if analyzer.data_node_classes:
        constructor_notes.append(f"DataNode subclasses: {', '.join(analyzer.data_node_classes)}")
    else:
        constructor_notes.append("No DataNode subclass found.")
        constructor_passed = False
    if analyzer.config_classes:
        constructor_notes.append(f"Config classes: {', '.join(analyzer.config_classes)}")
    else:
        constructor_notes.append("No BaseConfiguration/DataNodeConfiguration subclass found.")
        constructor_passed = False
    if analyzer.has_super_init_config:
        constructor_notes.append("Found super().__init__(config=...).")
    else:
        constructor_notes.append("Missing super().__init__(config=...).")
        constructor_passed = False
    if analyzer.uses_removed_legacy_patterns:
        constructor_notes.append("Uses removed legacy hashing patterns.")
        constructor_passed = False
    hard_fail_checks.append(build_hard_check("constructor-config-contract", constructor_passed, constructor_notes))

    hash_notes = []
    hash_passed = True
    if analyzer.invalid_hash_metadata:
        hash_notes.extend(analyzer.invalid_hash_metadata)
        hash_passed = False
    if analyzer.uses_removed_legacy_patterns:
        hash_notes.append("Removed hashing metadata detected.")
        hash_passed = False
    if analyzer.update_only_fields:
        hash_notes.append(f"update_only fields: {', '.join(sorted(analyzer.update_only_fields))}")
    if analyzer.runtime_only_fields:
        hash_notes.append(f"runtime_only fields: {', '.join(sorted(analyzer.runtime_only_fields))}")
    if not hash_notes:
        hash_notes.append("No explicit hash metadata violations detected.")
    hard_fail_checks.append(build_hard_check("hash-classification-contract", hash_passed, hash_notes))

    update_notes = []
    update_passed = True
    if analyzer.has_update_method:
        update_notes.append("Found update() method.")
    else:
        update_notes.append("No update() method found.")
        update_passed = False
    if analyzer.update_returns_none:
        update_notes.append("update() returns None.")
        update_passed = False
    if analyzer.update_calls_dataframe:
        update_notes.append("update() constructs a DataFrame.")
    elif analyzer.has_update_method:
        update_notes.append("No DataFrame construction detected in update().")
        update_passed = False
    hard_fail_checks.append(build_hard_check("update-return-contract", update_passed, update_notes))

    dataframe_notes = []
    dataframe_passed = True
    if analyzer.uses_time_index:
        dataframe_notes.append("Mentions time_index.")
    else:
        dataframe_notes.append("No time_index evidence found.")
        dataframe_passed = False
    if analyzer.uppercase_column_names:
        dataframe_notes.append(
            "Non-lowercase columns: " + ", ".join(sorted(analyzer.uppercase_column_names))
        )
        dataframe_passed = False
    else:
        dataframe_notes.append("No non-lowercase output columns detected.")
    if analyzer.column_names_too_long:
        dataframe_notes.append(
            "Columns longer than 63 chars: " + ", ".join(sorted(analyzer.column_names_too_long))
        )
        dataframe_passed = False
    else:
        dataframe_notes.append("No column names over 63 chars detected.")
    if analyzer.uses_datetime_payload_column:
        dataframe_notes.append("Detected datetime64 payload column usage.")
        dataframe_passed = False
    else:
        dataframe_notes.append("No forbidden datetime payload columns detected.")
    dataframe_notes.append("Heuristic assumes inf/-inf are normalized by the SDK validation path.")
    hard_fail_checks.append(build_hard_check("dataframe-validation-contract", dataframe_passed, dataframe_notes))

    multiindex_notes = []
    multiindex_passed = True
    asset_signals = (
        asset_index_required
        or analyzer.uses_asset_list
        or analyzer.uses_get_asset_list
        or analyzer.uses_multiindex
        or analyzer.uses_unique_identifier
        or analyzer.uses_asset_symbol
    )
    if asset_signals:
        if analyzer.uses_unique_identifier:
            multiindex_notes.append("Uses unique_identifier for asset indexing.")
        else:
            multiindex_notes.append("Asset-indexed response is missing unique_identifier.")
            multiindex_passed = False
        if analyzer.uses_asset_symbol:
            multiindex_notes.append("Uses stale asset_symbol naming.")
            multiindex_passed = False
        else:
            multiindex_notes.append("No stale asset_symbol usage detected.")
    else:
        multiindex_notes.append("Not an asset-indexed response; check not applicable.")
    hard_fail_checks.append(build_hard_check("multiindex-contract", multiindex_passed, multiindex_notes))

    duplicate_notes = []
    duplicate_passed = True
    if analyzer.mentions_duplicate_safe:
        duplicate_notes.append("Explicitly states duplicate index keys are not allowed.")
    elif analyzer.uses_drop_duplicates:
        duplicate_notes.append("Uses drop_duplicates; may be compensating for duplicate emissions.")
    else:
        duplicate_notes.append("No explicit duplicate-key violation detected.")
    hard_fail_checks.append(build_hard_check("duplicate-key-contract", duplicate_passed, duplicate_notes))

    for check in hard_fail_checks:
        if not check["passed"]:
            findings.append(
                {
                    "severity": "hard_fail",
                    "message": f"{check['id']} failed.",
                    "notes": check["notes"],
                }
            )

    quality_checks: list[dict] = []

    dataset_score = 0.0
    dataset_notes = []
    if analyzer.has_super_init_config and analyzer.config_classes:
        dataset_score += 0.35
        dataset_notes.append("Uses config-driven constructor pattern.")
    if analyzer.uses_identifier or analyzer.uses_node_metadata:
        dataset_score += 0.25
        dataset_notes.append("Provides identifier or published metadata.")
    if contains_any(analyzer.lowered, ["storage_hash", "update_hash", "dataset meaning", "updater scope"]):
        dataset_score += 0.2
        dataset_notes.append("Recognizes storage/update hash semantics.")
    if contains_any(analyzer.lowered, ["collision", "unique across", "stable identifier", "project_id"]):
        dataset_score += 0.2
        dataset_notes.append("Shows identifier collision awareness.")
    quality_checks.append(build_quality_check("dataset-contract", dataset_score, dataset_notes or ["No dataset-contract evidence found."]))

    incremental_score = 0.0
    incremental_notes = []
    if analyzer.uses_update_statistics:
        incremental_score += 0.55
        incremental_notes.append("Uses update_statistics.")
    if analyzer.uses_offset_start:
        incremental_score += 0.15
        incremental_notes.append("Mentions offset_start.")
    if contains_any(analyzer.lowered, ["empty pd.dataframe", "return pd.dataframe()", "temp_df.empty", "if last is not none"]):
        incremental_score += 0.15
        incremental_notes.append("Handles no-op / incremental update path.")
    if analyzer.explicit_full_history_pattern:
        incremental_score = max(0.0, incremental_score - 0.3)
        incremental_notes.append("Suggests full-history behavior.")
    if contains_any(analyzer.lowered, ["backfill", "controlled overwrite", "force_update"]):
        incremental_score += 0.15
        incremental_notes.append("Mentions controlled backfill/update behavior.")
    quality_checks.append(build_quality_check("incremental-update", incremental_score, incremental_notes or ["No incremental-update evidence found."]))

    dependency_score = 0.0
    dependency_notes = []
    if analyzer.dependencies_in_init:
        dependency_score += 0.4
        dependency_notes.append("Instantiates dependencies in __init__.")
    if analyzer.has_dependencies_method and analyzer.dependencies_return_dict:
        dependency_score += 0.4
        dependency_notes.append("dependencies() returns a dict.")
    if analyzer.dependency_keys:
        dependency_score += 0.1
        dependency_notes.append("Dependency keys: " + ", ".join(sorted(set(analyzer.dependency_keys))))
    if analyzer.dependencies_built_in_update:
        dependency_score = max(0.0, dependency_score - 0.35)
        dependency_notes.append("Builds dependency-like objects inside update().")
    quality_checks.append(build_quality_check("dependency-design", dependency_score, dependency_notes or ["No dependency-design evidence found."]))

    metadata_score = 0.0
    metadata_notes = []
    if analyzer.uses_node_metadata or analyzer.uses_get_table_metadata:
        metadata_score += 0.35
        metadata_notes.append("Provides table metadata.")
    if analyzer.uses_records or analyzer.uses_get_column_metadata or analyzer.uses_record_definition:
        metadata_score += 0.35
        metadata_notes.append("Provides column metadata.")
    if analyzer.column_names:
        metadata_score += 0.15
        metadata_notes.append("Defines output columns explicitly.")
    if contains_any(analyzer.lowered, ["description", "search", "discovery", "dtype"]):
        metadata_score += 0.15
        metadata_notes.append("Metadata supports discovery or dtype clarity.")
    quality_checks.append(build_quality_check("metadata-quality", metadata_score, metadata_notes or ["No metadata-quality evidence found."]))

    asset_score = 0.0
    asset_notes = []
    if asset_signals:
        if analyzer.uses_unique_identifier:
            asset_score += 0.35
            asset_notes.append("Uses unique_identifier.")
        if analyzer.uses_get_asset_list or analyzer.uses_asset_list:
            asset_score += 0.3
            asset_notes.append("Uses asset_list/get_asset_list.")
        if analyzer.uses_asset_registration:
            asset_score += 0.2
            asset_notes.append("Handles asset registration/resolution.")
        if contains_any(analyzer.lowered, ["asset universe is scope", "asset universe", "not include asset universe in storage_hash"]):
            asset_score += 0.15
            asset_notes.append("Separates asset scope from dataset meaning.")
    else:
        asset_score = 1.0
        asset_notes.append("Not asset-indexed; check treated as not applicable.")
    if not asset_notes:
        asset_notes.append("No valid asset-index discipline evidence found.")
    quality_checks.append(build_quality_check("asset-index-discipline", asset_score, asset_notes))

    testing_score = 0.0
    testing_notes = []
    if analyzer.uses_hash_namespace:
        testing_score += 0.6
        testing_notes.append("Uses hash_namespace.")
    if analyzer.uses_test_node:
        testing_score += 0.2
        testing_notes.append("Mentions test_node shortcut.")
    if contains_any(analyzer.lowered, ["first validation run", "namespace first", "isolated testing", "pytest_case"]):
        testing_score += 0.2
        testing_notes.append("Frames namespace as first validation/isolation step.")
    quality_checks.append(build_quality_check("testing-isolation", testing_score, testing_notes or ["No testing/isolation evidence found."]))

    hygiene_score = 0.0
    hygiene_notes = []
    if analyzer.uses_time_index:
        hygiene_score += 0.2
        hygiene_notes.append("Uses time_index.")
    if not analyzer.uppercase_column_names:
        hygiene_score += 0.2
        hygiene_notes.append("No uppercase columns detected.")
    if not analyzer.column_names_too_long:
        hygiene_score += 0.2
        hygiene_notes.append("No overlength columns detected.")
    if not analyzer.uses_datetime_payload_column:
        hygiene_score += 0.2
        hygiene_notes.append("No datetime payload columns detected.")
    if analyzer.mentions_stable_dtypes or contains_any(analyzer.lowered, ["float64", "int64", "string", "dtype"]):
        hygiene_score += 0.1
        hygiene_notes.append("Mentions dtype stability.")
    if analyzer.mentions_sorted_index:
        hygiene_score += 0.1
        hygiene_notes.append("Mentions sorted index.")
    quality_checks.append(build_quality_check("dataframe-hygiene", hygiene_score, hygiene_notes or ["No dataframe-hygiene evidence found."]))

    for item in quality_checks:
        if item["score"] < 0.5:
            findings.append(
                {
                    "severity": "major_quality_issue" if item["score"] < 0.25 else "minor_quality_issue",
                    "message": f"{item['id']} scored {item['score']:.2f}.",
                    "notes": item["notes"],
                }
            )

    hard_fail_passed = all(check["passed"] for check in hard_fail_checks)
    raw_total = round(sum(item["weighted_score"] for item in quality_checks), 4)
    passing_score = float(rubric.get("passing_score", 0.85))
    passed = hard_fail_passed and raw_total >= passing_score

    limitations = [
        "This is a heuristic evaluator based on response text and Python code blocks.",
        "Absence of an explicit violation is treated as pass for some hard checks.",
        "It cannot prove runtime correctness without executing the node.",
    ]
    if analyzer.parse_errors:
        limitations.append("Some Python code blocks could not be parsed: " + "; ".join(analyzer.parse_errors))

    return {
        "method": "rule-based-checklist",
        "case_id": case_id,
        "raw_score": raw_total,
        "total_score": raw_total,
        "passing_score": passing_score,
        "passed": passed,
        "hard_fail_passed": hard_fail_passed,
        "hard_fail_checks": hard_fail_checks,
        "quality_checks": quality_checks,
        "findings": findings,
        "limitations": limitations,
    }


def evaluate_case(case_path: Path, response_path: Path) -> dict:
    case_payload = load_yaml(case_path / "case.yaml")
    rubric = load_yaml(case_path / "rubric.yaml")
    response_text = response_path.read_text(encoding="utf-8")
    case_id = case_payload["id"]
    skill_path = case_payload.get("skill_path", "")

    if case_id == "or-001-recurring-artifact-job":
        return score_or_001(response_text, rubric)

    if case_id.startswith("dn-") or skill_path == "data_publishing/data_nodes":
        return score_datanode_case(case_payload, rubric, response_text)

    if case_id.startswith("st-"):
        return score_simpletable_case(case_payload, rubric, response_text)

    if case_id.startswith("stu-"):
        return score_simpletable_updater_case(case_payload, rubric, response_text)

    raise SystemExit(f"No evaluator is registered for case {case_id!r}.")


def main() -> int:
    args = build_parser().parse_args()
    case_path = args.case_path.resolve()
    response_path = args.response_path.resolve()
    evaluation = evaluate_case(case_path, response_path)
    evaluation["evaluator"] = {
        "name": args.evaluator_name,
        "kind": args.evaluator_kind,
        "evaluated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
    }

    payload = json.dumps(evaluation, indent=2, ensure_ascii=False) + "\n"
    if args.output_path:
        args.output_path.parent.mkdir(parents=True, exist_ok=True)
        args.output_path.write_text(payload, encoding="utf-8")
    else:
        print(payload, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
