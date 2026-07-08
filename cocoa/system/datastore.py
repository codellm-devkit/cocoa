"""Service -> datastore edges: Redis client calls + SQL/ORM, all statically derived."""
from __future__ import annotations

import re

import sqlglot
from sqlglot import exp

from cocoa.system.facts import ServiceFacts
from cocoa.system.models import Edge, EdgeKind, Node, NodeKind, Provenance
from cocoa.system.wiring import Workload

_REDIS_EVIDENCE = re.compile(
    r"(?<![a-z0-9])(?:redis|jedis|ioredis|stackexchange\.redis)"
    r"(?:template|client|pool|conn|connection|db)?(?![a-z0-9])"
)
_REDIS_READS = {
    "get", "hget", "hgetall", "mget", "lrange", "smembers", "exists",
    "scan", "keys", "ttl", "zrange", "sismember", "llen",
}
# No explicit writes set: classification is reads-set-or-conservative-WRITES,
# i.e. anything not a known read command is treated as a write.
_ADDR = re.compile(r"^([a-z0-9][a-z0-9.-]*):\d+$")
_STR_LIT = re.compile(r'"([^"]+)"|\'([^\']+)\'')
_SQL_HINT = re.compile(r"(?is)\b(select\s.+?\sfrom\s|insert\s+into\s|update\s+\w+\s+set\s|delete\s+from\s)")
_TABLENAME = re.compile(r"__tablename__\s*=\s*[\"'](\w+)[\"']")
_JPA_TABLE = re.compile(r"@Table\s*\(\s*name\s*=\s*[\"'](\w+)[\"']")
_TABLE_STOPWORDS = {"the", "your", "a", "an", "my", "our", "their", "this", "that", "it", "us", "them"}


def _redis_host(service: str, workloads: list[Workload]) -> tuple[str, bool]:
    for w in workloads:
        if w.name == service:
            for var, val in w.env.items():
                m = _ADDR.match(val.strip())
                if m and "REDIS" in var.upper().split("_"):
                    return m.group(1), True
    return service, False


def _first_literal(args: list[str]) -> str | None:
    """Only args[0] can be a key literal; later positional args (TTLs, values,
    etc.) are never keys and must not be fabricated into key nodes."""
    if not args:
        return None
    m = _STR_LIT.search(args[0])
    if m:
        return m.group(1) or m.group(2)
    return None


def _plausible_select(tree: exp.Expression) -> bool:
    """Reject prose that parses as SELECT: require structural SQL signals."""
    exprs = tree.expressions or []
    structural = (
        len(exprs) > 1
        or any(isinstance(e, (exp.Star, exp.Func)) for e in exprs)
        or any(tree.args.get(k) for k in ("where", "joins", "group", "order", "limit"))
    )
    return structural


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
        if is_read and not _plausible_select(tree):
            continue
        for t in tree.find_all(exp.Table):
            if t.name and t.name.lower() not in _TABLE_STOPWORDS:
                out.append((t.name, is_read))
    return out


def extract_data_access(
    facts_by_service: dict[str, ServiceFacts], workloads: list[Workload]
) -> tuple[list[Node], list[Edge]]:
    nodes: dict[str, Node] = {}
    edges: list[Edge] = []
    seen_orm: set[tuple[str, str]] = set()

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
            if not _REDIS_EVIDENCE.search(evidence):
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
                    table = m.group(1)
                    key = (service, table)
                    if key in seen_orm:
                        # Upstream flattens class-level @Table/__tablename__ onto every
                        # method's FunctionFact; only the first declaring function emits.
                        continue
                    seen_orm.add(key)
                    add_table_edges(fid, fn.file, table,
                                    {EdgeKind.READS, EdgeKind.WRITES}, via="orm")
    return list(nodes.values()), edges
