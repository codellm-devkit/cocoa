"""Tolerant .proto parser: services, rpcs, messages, fields — enough for stitching."""
from __future__ import annotations

import re
from pathlib import Path

from pydantic import BaseModel, Field

_COMMENT = re.compile(r"//[^\n]*|/\*.*?\*/", re.S)
_PACKAGE = re.compile(r"\bpackage\s+([\w.]+)\s*;")
_BLOCK = re.compile(r"\b(service|message)\s+(\w+)\s*\{")
_RPC = re.compile(
    r"\brpc\s+(\w+)\s*\(\s*(?:stream\s+)?([\w.]+)\s*\)\s*returns\s*\(\s*(?:stream\s+)?([\w.]+)\s*\)"
)
_FIELD = re.compile(r"\s*(repeated\s+)?([\w.]+)\s+(\w+)\s*=\s*(\d+)", re.M)
_SCALARS = {
    "double", "float", "int32", "int64", "uint32", "uint64", "sint32", "sint64",
    "fixed32", "fixed64", "sfixed32", "sfixed64", "bool", "string", "bytes",
}


class ProtoField(BaseModel):
    name: str
    type: str
    number: int
    repeated: bool = False


class ProtoRpc(BaseModel):
    name: str
    request: str
    response: str


class ProtoService(BaseModel):
    name: str
    rpcs: list[ProtoRpc] = Field(default_factory=list)


class ProtoMessage(BaseModel):
    name: str
    fields: list[ProtoField] = Field(default_factory=list)


class ProtoModel(BaseModel):
    package: str = ""
    services: dict[str, ProtoService] = Field(default_factory=dict)
    messages: dict[str, ProtoMessage] = Field(default_factory=dict)


def _matching_brace(text: str, open_idx: int) -> int:
    depth = 0
    for i in range(open_idx, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return i
    return len(text) - 1


def _qualify(name: str, package: str) -> str:
    if "." in name or not package:
        return name
    return f"{package}.{name}"


_NESTED_BLOCK = re.compile(r"\b(?:message|enum)\s+\w+\s*\{")


def _strip_nested_blocks(body: str) -> str:
    """Splice out nested message/enum sub-blocks so their fields don't leak into the parent.

    oneof blocks are deliberately kept — their members are real parent fields.
    """
    while (m := _NESTED_BLOCK.search(body)) is not None:
        close = _matching_brace(body, m.end() - 1)
        body = body[: m.start()] + body[close + 1:]
    return body


def parse_proto(text: str) -> ProtoModel:
    text = _COMMENT.sub("", text)
    pkg_m = _PACKAGE.search(text)
    package = pkg_m.group(1) if pkg_m else ""
    model = ProtoModel(package=package)
    for m in _BLOCK.finditer(text):
        kind, name = m.group(1), m.group(2)
        body = text[m.end(): _matching_brace(text, m.end() - 1)]
        fqn = _qualify(name, package)
        if kind == "service":
            svc = ProtoService(name=fqn)
            for r in _RPC.finditer(body):
                svc.rpcs.append(ProtoRpc(
                    name=r.group(1),
                    request=_qualify(r.group(2), package),
                    response=_qualify(r.group(3), package),
                ))
            model.services[fqn] = svc
        else:
            msg = ProtoMessage(name=fqn)
            for f in _FIELD.finditer(_strip_nested_blocks(body)):
                ftype = f.group(2)
                if ftype in ("option", "reserved", "oneof", "map", "enum", "message"):
                    continue
                msg.fields.append(ProtoField(
                    name=f.group(3),
                    type=ftype if ftype in _SCALARS else _qualify(ftype, package),
                    number=int(f.group(4)),
                    repeated=bool(f.group(1)),
                ))
            model.messages[fqn] = msg
    return model


def parse_proto_files(paths: list[Path]) -> ProtoModel:
    merged = ProtoModel()
    for p in paths:
        one = parse_proto(Path(p).read_text(encoding="utf-8", errors="replace"))
        merged.package = merged.package or one.package
        merged.services.update(one.services)
        merged.messages.update(one.messages)
    return merged


def rpcs_touching_field(model: ProtoModel, field_fqn: str) -> set[tuple[str, str]]:
    """field 'pkg.Msg.field' -> all (service_fqn, rpc_name) whose req/resp reach Msg."""
    msg_fqn, _, field_name = field_fqn.rpartition(".")
    if msg_fqn not in model.messages or not any(
        f.name == field_name for f in model.messages[msg_fqn].fields
    ):
        return set()
    # reverse containment: which messages (transitively) contain msg_fqn
    containers: dict[str, set[str]] = {}
    for parent, msg in model.messages.items():
        for f in msg.fields:
            if f.type in model.messages:
                containers.setdefault(f.type, set()).add(parent)
    reach = {msg_fqn}
    frontier = [msg_fqn]
    while frontier:
        cur = frontier.pop()
        for parent in containers.get(cur, ()):
            if parent not in reach:
                reach.add(parent)
                frontier.append(parent)
    hits: set[tuple[str, str]] = set()
    for svc in model.services.values():
        for rpc in svc.rpcs:
            if rpc.request in reach or rpc.response in reach:
                hits.add((svc.name, rpc.name))
    return hits
