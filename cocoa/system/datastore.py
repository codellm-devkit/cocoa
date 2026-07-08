"""Service -> datastore edges: Redis client calls + SQL/ORM, all statically derived."""
from __future__ import annotations

import re

import sqlglot
from sqlglot import exp

from cocoa.system.facts import ServiceFacts
from cocoa.system.models import Edge, EdgeKind, Node, NodeKind, Provenance
from cocoa.system.wiring import Workload

_REDIS_TOKENS = ("redis", "jedis", "ioredis", "stackexchange.redis")
_REDIS_READS = {
    "get", "hget", "hgetall", "mget", "lrange", "smembers", "exists",
    "scan", "keys", "ttl", "zrange", "sismember", "llen",
}
_REDIS_WRITES = {
    "set", "setex", "hset", "hmset", "del", "delete", "expire", "lpush",
    "rpush", "sadd", "srem", "incr", "decr", "zadd", "flushdb",
}
_ADDR = re.compile(r"^([a-z0-9][a-z0-9.-]*):\d+$")
_STR_LIT = re.compile(r'"([^"]+)"|\'([^\']+)\'')
_SQL_HINT = re.compile(r"(?is)\b(select\s.+?\sfrom\s|insert\s+into\s|update\s+\w+\s+set\s|delete\s+from\s)")
_TABLENAME = re.compile(r"__tablename__\s*=\s*[\"'](\w+)[\"']")
_JPA_TABLE = re.compile(r"@Table\s*\(\s*name\s*=\s*[\"'](\w+)[\"']")


def _redis_host(service: str, workloads: list[Workload]) -> tuple[str, bool]:
    for w in workloads:
        if w.name == service:
            for var, val in w.env.items():
                m = _ADDR.match(val.strip())
                if "REDIS" in var.upper() and m:
                    return m.group(1), True
    return service, False


def _first_literal(args: list[str]) -> str | None:
    for a in args:
        m = _STR_LIT.search(a)
        if m:
            return m.group(1) or m.group(2)
    return None


def _sql_tables(text: str) -> list[tuple[str, bool]]:
    """-> [(table, is_read)] for every SQL string literal found in text."""
    out: list[tuple[str, bool]] = []
    for m in _STR_LIT.finditer(text):
        sql = m.group(1) or m.group(2)
        if not sql or not _SQL_HINT.search(sql):
            continue
        try:
            tree = sqlglot.parse_one(sql, error_level=sqlglot.ErrorLevel.IGNORE)
        except Exception:
            continue
        if tree is None:
            continue
        is_read = isinstance(tree, exp.Select)
        for t in tree.find_all(exp.Table):
            if t.name:
                out.append((t.name, is_read))
    return out


def extract_data_access(
    facts_by_service: dict[str, ServiceFacts], workloads: list[Workload]
) -> tuple[list[Node], list[Edge]]:
    nodes: dict[str, Node] = {}
    edges: list[Edge] = []

    def add_node(node: Node) -> None:
        nodes.setdefault(node.id, node)

    def add_table_edges(fid: str, file: str | None, table: str, kinds: set[EdgeKind],
                        via: str = "sql") -> None:
        add_node(Node(id=f"tbl:{table}", kind=NodeKind.TABLE))
        for k in kinds:
            edges.append(Edge(source=fid, target=f"tbl:{table}", kind=k,
                              provenance=Provenance.DERIVED_STATIC,
                              site_file=file, attrs={"via": via}))

    for service, sf in facts_by_service.items():
        # --- Redis via call sites
        for cs in sf.call_sites:
            evidence = f"{cs.receiver} {cs.receiver_type} {cs.callee_hint}".lower()
            if not any(tok in evidence for tok in _REDIS_TOKENS):
                continue
            cmd = cs.method_name.lower()
            kind = EdgeKind.READS if cmd in _REDIS_READS else EdgeKind.WRITES
            host, resolved = _redis_host(service, workloads)
            ds = f"ds:redis:{host}"
            add_node(Node(id=ds, kind=NodeKind.DATASTORE, service=None,
                          attrs={"type": "redis", "resolved": str(resolved).lower()}))
            fn = sf.functions.get(cs.caller_id)
            edges.append(Edge(source=cs.caller_id, target=ds, kind=kind,
                              provenance=Provenance.DERIVED_STATIC,
                              site_file=fn.file if fn else None, site_line=cs.line,
                              attrs={"op": cmd}))
            lit = _first_literal(cs.args)
            if lit:
                kid = f"key:{lit}"
                add_node(Node(id=kid, kind=NodeKind.KEY_PATTERN, attrs={"datastore": ds}))
                edges.append(Edge(source=cs.caller_id, target=kid, kind=kind,
                                  provenance=Provenance.DERIVED_STATIC, site_line=cs.line))
        # --- SQL + ORM via code text
        for fid, fn in sf.functions.items():
            texts = [fn.code or ""]
            texts += [a for cs in sf.call_sites if cs.caller_id == fid for a in cs.args]
            blob = "\n".join(texts)
            for table, is_read in _sql_tables(blob):
                add_table_edges(fid, fn.file, table,
                                {EdgeKind.READS if is_read else EdgeKind.WRITES})
            for rx in (_TABLENAME, _JPA_TABLE):
                for m in rx.finditer(blob + "\n" + "\n".join(fn.annotations)):
                    add_table_edges(fid, fn.file, m.group(1),
                                    {EdgeKind.READS, EdgeKind.WRITES}, via="orm")
    return list(nodes.values()), edges
