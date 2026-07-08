"""Normalized per-service facts + adapters from each analyzer's output shape."""
from __future__ import annotations

from pydantic import BaseModel, Field


class FunctionFact(BaseModel):
    id: str
    service: str
    name: str
    qualified: str
    file: str | None = None
    start_line: int | None = None
    end_line: int | None = None
    code: str | None = None
    annotations: list[str] = Field(default_factory=list)


class CallSiteFact(BaseModel):
    caller_id: str
    method_name: str
    receiver: str = ""
    receiver_type: str = ""
    callee_hint: str = ""
    line: int | None = None
    args: list[str] = Field(default_factory=list)       # literal exprs (Java only)
    arg_types: list[str] = Field(default_factory=list)


class ServiceFacts(BaseModel):
    service: str
    language: str
    functions: dict[str, FunctionFact] = Field(default_factory=dict)
    call_edges: list[tuple[str, str]] = Field(default_factory=list)
    call_sites: list[CallSiteFact] = Field(default_factory=list)


def _fid(service: str, qualified: str) -> str:
    return f"fn:{service}/{qualified}"


def _add_sites(out: ServiceFacts, fid: str, call_sites: list[dict] | None) -> None:
    for cs in call_sites or []:
        out.call_sites.append(CallSiteFact(
            caller_id=fid,
            method_name=cs.get("method_name", ""),
            receiver=cs.get("receiver_expr", "") or "",
            receiver_type=cs.get("receiver_type", "") or "",
            callee_hint=cs.get("callee_signature", "") or "",
            line=cs.get("start_line"),
            args=list(cs.get("argument_expr") or []),
            arg_types=list(cs.get("argument_types") or []),
        ))


def _java_endpoint(d: dict) -> str | None:
    if "klass" in d:  # validated JMethodDetail dump
        return f"{d['klass']}.{d['method']['signature']}"
    if "type_declaration" in d:  # raw analysis.json CallableVertex
        return f"{d['type_declaration']}.{d['signature']}"
    return None


def from_java(dump: dict, service: str) -> ServiceFacts:
    out = ServiceFacts(service=service, language="java")
    for file_path, cu in (dump.get("symbol_table") or {}).items():
        for fqcn, typ in (cu.get("type_declarations") or {}).items():
            for sig, meth in (typ.get("callable_declarations") or {}).items():
                qualified = f"{fqcn}.{meth.get('signature', sig)}"
                fid = _fid(service, qualified)
                out.functions[fid] = FunctionFact(
                    id=fid, service=service, name=meth.get("signature", sig),
                    qualified=qualified, file=file_path,
                    start_line=meth.get("start_line"), end_line=meth.get("end_line"),
                    code=meth.get("code"),
                    annotations=list(typ.get("annotations") or []) + list(meth.get("annotations") or []),
                )
                _add_sites(out, fid, meth.get("call_sites"))
    for e in dump.get("call_graph") or []:
        s, t = _java_endpoint(e.get("source", {})), _java_endpoint(e.get("target", {}))
        if s and t:
            sid, tid = _fid(service, s), _fid(service, t)
            if sid in out.functions:
                out.call_edges.append((sid, tid))
    return out


def _from_sigmap(out: ServiceFacts, file_path: str, callables: dict) -> None:
    for sig, c in (callables or {}).items():
        qualified = c.get("signature", sig)
        fid = _fid(out.service, qualified)
        out.functions[fid] = FunctionFact(
            id=fid, service=out.service, name=c.get("name", qualified),
            qualified=qualified, file=c.get("path") or file_path,
            start_line=c.get("start_line"), end_line=c.get("end_line"),
            code=c.get("code"),
            annotations=[str(d) for d in (c.get("decorators") or [])],
        )
        _add_sites(out, fid, c.get("call_sites"))


def _identity_edges(out: ServiceFacts, edges: list[dict] | None) -> None:
    for e in edges or []:
        sid, tid = _fid(out.service, e.get("source", "")), _fid(out.service, e.get("target", ""))
        if sid in out.functions and tid in out.functions:
            out.call_edges.append((sid, tid))


def from_python(dump: dict, service: str) -> ServiceFacts:
    app = dump.get("application", dump)  # unwrap v2 envelope
    out = ServiceFacts(service=service, language="python")
    for file_path, mod in (app.get("symbol_table") or {}).items():
        _from_sigmap(out, file_path, mod.get("functions"))
        for _, klass in (mod.get("classes") or {}).items():
            _from_sigmap(out, file_path, klass.get("methods"))
    _identity_edges(out, app.get("call_graph"))
    return out


def from_typescript(dump: dict, service: str) -> ServiceFacts:
    out = ServiceFacts(service=service, language="typescript")
    for file_path, mod in (dump.get("symbol_table") or {}).items():
        _from_sigmap(out, file_path, mod.get("functions"))
        for _, klass in (mod.get("classes") or {}).items():
            _from_sigmap(out, file_path, klass.get("methods"))
    _identity_edges(out, dump.get("call_graph"))
    return out


def from_go(raw: dict, service: str) -> ServiceFacts:
    out = ServiceFacts(service=service, language="go")
    for file_path, f in (raw.get("symbol_table") or {}).items():
        _from_sigmap(out, file_path, f.get("functions"))
        for _, typ in (f.get("classes") or {}).items():
            _from_sigmap(out, file_path, typ.get("methods"))
    _identity_edges(out, raw.get("call_graph"))
    return out
