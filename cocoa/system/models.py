"""Core system-graph models: the one persistent currency of cocoa.system."""
from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field


class Provenance(str, Enum):
    DERIVED_STATIC = "DERIVED-STATIC"
    INFERRED = "INFERRED"


class NodeKind(str, Enum):
    SERVICE = "service"
    K8S_WORKLOAD = "k8s_workload"
    FUNCTION = "function"
    RPC_ENDPOINT = "rpc_endpoint"
    PROTO_MESSAGE = "proto_message"
    PROTO_FIELD = "proto_field"
    DATASTORE = "datastore"
    TABLE = "table"
    KEY_PATTERN = "key_pattern"


class EdgeKind(str, Enum):
    CALLS = "CALLS"            # fn -> fn (intra-service)
    RPC_CALLS = "RPC_CALLS"    # client fn -> rpc_endpoint
    HANDLES = "HANDLES"        # rpc_endpoint -> server handler fn
    READS = "READS"            # fn -> datastore/table/key_pattern
    WRITES = "WRITES"          # fn -> datastore/table/key_pattern
    HOSTS = "HOSTS"            # service -> rpc_endpoint
    USES_TYPE = "USES_TYPE"    # rpc_endpoint -> proto_message (req/resp)
    HAS_FIELD = "HAS_FIELD"    # proto_message -> proto_field
    CONTAINS = "CONTAINS"      # proto_message -> proto_message (field of message type)


class Node(BaseModel):
    id: str
    kind: NodeKind
    service: Optional[str] = None
    file: Optional[str] = None
    line: Optional[int] = None
    attrs: dict[str, str] = Field(default_factory=dict)


class Edge(BaseModel):
    source: str
    target: str
    kind: EdgeKind
    provenance: Provenance
    site_file: Optional[str] = None
    site_line: Optional[int] = None
    attrs: dict[str, str] = Field(default_factory=dict)


class Skipped(BaseModel):
    service: str
    language: str
    reason: str


class SystemGraph(BaseModel):
    version: str = "1"
    root: str
    nodes: list[Node] = Field(default_factory=list)
    edges: list[Edge] = Field(default_factory=list)
    skipped: list[Skipped] = Field(default_factory=list)

    def node_ids(self) -> set[str]:
        return {n.id for n in self.nodes}

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.model_dump_json(indent=1), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "SystemGraph":
        return cls.model_validate_json(Path(path).read_text(encoding="utf-8"))
