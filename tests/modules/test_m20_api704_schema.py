"""Row704 scoped API-documentation schema generator tests (OpenAPI 3.1 subset)."""
import copy
import hashlib
import json
import math

import jsonschema
import pytest

from app.modules.m20_general_cognitive_worker import openapi704 as mod
from app.modules.m20_general_cognitive_worker.openapi704 import generate_openapi


def base():
    return {
        "info": {"title": "Pets", "version": "1.0.0"},
        "schemas": {
            "Pet": {"source_ref": "src/models.py:10", "schema": {
                "type": "object",
                "required": ["id", "name"],
                "properties": {
                    "id": {"type": "integer", "minimum": 1},
                    "name": {"type": "string", "minLength": 1, "maxLength": 40},
                    "tag": {"type": "string"},
                    "owner": {"type": "string", "nullable": True},
                    "score": {"type": "number"},
                    "alive": {"type": "boolean"},
                    "labels": {"type": "array", "items": {"type": "string"}},
                }}},
            "NewPet": {"source_ref": "src/models.py:30", "schema": {
                "type": "object", "required": ["name"],
                "properties": {"name": {"type": "string", "minLength": 1}, "tag": {"type": "string"}}}},
        },
        "operations": [
            {"operation_id": "getPet", "method": "get", "path": "/pets/{petId}",
             "summary": "Fetch a pet", "source_ref": "src/routes.py:5",
             "parameters": [{"name": "petId", "in": "path", "required": True, "schema": {"type": "integer"}, "example": 7},
                            {"name": "verbose", "in": "query", "schema": {"type": "boolean"}, "example": True}],
             "responses": {"200": {"description": "ok", "schema": {"$ref": "#/components/schemas/Pet"},
                                   "example": {"id": 7, "name": "Rex", "owner": None}},
                           "404": {"description": "missing"}}},
            {"operation_id": "createPet", "method": "post", "path": "/pets",
             "summary": "Create a pet", "source_ref": "src/routes.py:20",
             "request_body": {"required": True, "schema": {"$ref": "#/components/schemas/NewPet"},
                              "example": {"name": "Rex"}},
             "responses": {"201": {"description": "created", "schema": {"$ref": "#/components/schemas/Pet"},
                                   "example": {"id": 1, "name": "Rex"}}}},
        ],
    }


def refuse(d, match=None):
    with pytest.raises(ValueError, match=match):
        generate_openapi(d)


# ---- known answer ----
def test_known_answer_document_shape():
    r = generate_openapi(base())
    doc = r["openapi"]
    assert doc["openapi"] == "3.1.0"
    assert doc["info"] == {"title": "Pets", "version": "1.0.0"}
    assert sorted(doc["paths"]) == ["/pets", "/pets/{petId}"]
    get = doc["paths"]["/pets/{petId}"]["get"]
    assert get["operationId"] == "getPet"
    assert get["parameters"][0] == {"name": "petId", "in": "path", "required": True,
                                    "schema": {"type": "integer"}, "example": 7}
    assert get["parameters"][1]["required"] is False
    assert get["responses"]["200"]["content"]["application/json"]["schema"] == {"$ref": "#/components/schemas/Pet"}
    assert get["responses"]["404"] == {"description": "missing"}
    pet = doc["components"]["schemas"]["Pet"]
    assert pet["required"] == ["id", "name"]
    assert pet["properties"]["owner"]["type"] == ["string", "null"]
    assert pet["properties"]["tag"]["type"] == "string"
    post = doc["paths"]["/pets"]["post"]
    assert post["requestBody"]["required"] is True
    assert post["requestBody"]["content"]["application/json"]["example"] == {"name": "Rex"}


def test_required_and_nullable_are_distinct():
    pet = generate_openapi(base())["openapi"]["components"]["schemas"]["Pet"]
    assert "owner" not in pet["required"] and pet["properties"]["owner"]["type"] == ["string", "null"]
    d = base()
    d["schemas"]["Pet"]["schema"]["required"].append("owner")
    refuse(d, "required")  # createPet response example omits the now-required owner
    d["operations"][1]["responses"]["201"]["example"]["owner"] = None
    pet = generate_openapi(d)["openapi"]["components"]["schemas"]["Pet"]
    assert "owner" in pet["required"] and pet["properties"]["owner"]["type"] == ["string", "null"]
    # nullable example: null ok on nullable, refused on non-nullable
    d = base()
    d["operations"][1]["request_body"]["example"] = {"name": None}
    refuse(d, "example")


def test_output_validates_against_independent_jsonschema_oracle():
    r = generate_openapi(base())
    doc = r["openapi"]
    comps = doc["components"]["schemas"]
    resolver_doc = {"components": {"schemas": comps}}
    for name, s in comps.items():
        jsonschema.Draft202012Validator.check_schema(s)
    # every example validates under jsonschema with the refs resolved against the doc
    for op in (o for p in doc["paths"].values() for o in p.values()):
        for code, resp in op["responses"].items():
            for media in resp.get("content", {}).values():
                if "example" in media:
                    sch = dict(media["schema"]); sch.update(resolver_doc)
                    jsonschema.validate(media["example"], sch, cls=jsonschema.Draft202012Validator)
    bad = {"id": "7", "name": "Rex"}
    sch = {"$ref": "#/components/schemas/Pet", **resolver_doc}
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(bad, sch, cls=jsonschema.Draft202012Validator)


def test_client_examples_validated_and_returned():
    r = generate_openapi(base())
    ids = {(e["operation_id"], e["kind"], e.get("name") or e.get("status")) for e in r["client_examples"]}
    assert ("getPet", "parameter", "petId") in ids
    assert ("getPet", "response", "200") in ids
    assert ("createPet", "request", None) in ids
    assert all(e["valid"] is True for e in r["client_examples"])


def test_roundtrip_and_deterministic_serialization():
    r = generate_openapi(base())
    assert json.loads(r["canonical_json"]) == r["openapi"]
    assert r["canonical_json"] == json.dumps(r["openapi"], sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)
    assert r["sha256"] == hashlib.sha256(r["canonical_json"].encode()).hexdigest()
    d2 = base()
    d2["operations"].reverse()
    d2["schemas"] = dict(reversed(list(d2["schemas"].items())))
    r2 = generate_openapi(d2)
    assert r2["canonical_json"] == r["canonical_json"]
    assert r2["source_trace"] == r["source_trace"]
    assert generate_openapi(base())["canonical_json"] == r["canonical_json"]


def test_source_trace_sorted_and_complete():
    r = generate_openapi(base())
    refs = [t["source_ref"] for t in r["source_trace"]]
    assert refs == sorted(refs) and len(refs) == 4
    assert {"src/models.py:10", "src/routes.py:5"} <= set(refs)
    kinds = {t["kind"] for t in r["source_trace"]}
    assert kinds == {"schema", "operation"}


def test_no_live_implementation_claim():
    r = generate_openapi(base())
    assert r["implementation_verified"] is False
    assert any("live implementation" in x for x in r["limits"])
    assert "implementation_verified" not in r["openapi"]


def test_source_ref_required_and_nonblank():
    d = base(); del d["operations"][0]["source_ref"]; refuse(d, "source_ref")
    d = base(); d["operations"][0]["source_ref"] = "  "; refuse(d, "source_ref")
    d = base(); del d["schemas"]["Pet"]["source_ref"]; refuse(d, "source_ref")


# ---- path/param consistency ----
def test_path_param_must_be_declared_required_path():
    d = base(); d["operations"][0]["parameters"].pop(0); refuse(d, "path")
    d = base(); d["operations"][0]["parameters"][0]["required"] = False; refuse(d, "required")
    d = base(); d["operations"][0]["path"] = "/pets"; refuse(d, "path")  # petId declared but not in template
    d = base(); d["operations"][0]["parameters"][0]["name"] = "id"; refuse(d, "path")
    d = base(); d["operations"][0]["parameters"].append(copy.deepcopy(d["operations"][0]["parameters"][0])); refuse(d, "duplicate")
    d = base(); d["operations"][0]["path"] = "/pets/{petId}/{petId}"; refuse(d, "path")
    d = base(); d["operations"][0]["path"] = "/pets/{}"; refuse(d, "path")
    d = base(); d["operations"][0]["path"] = "pets"; refuse(d, "path")


def test_duplicate_method_path_and_operation_id():
    d = base(); d["operations"][1].update(method="get", path="/pets/{petId}")
    d["operations"][1].pop("request_body"); d["operations"][1]["parameters"] = copy.deepcopy(d["operations"][0]["parameters"])
    refuse(d, "duplicate")
    d = base(); d["operations"][1]["operation_id"] = "getPet"; refuse(d, "duplicate")
    # templates differing only in placeholder name are the same path
    d = base()
    d["operations"].append({"operation_id": "other", "method": "get", "path": "/pets/{id}", "summary": "x",
                            "source_ref": "s", "parameters": [{"name": "id", "in": "path", "required": True, "schema": {"type": "string"}}],
                            "responses": {"200": {"description": "ok"}}})
    refuse(d, "duplicate")


def test_dangling_and_malformed_refs_and_recursion_refuse():
    d = base(); d["operations"][0]["responses"]["200"]["schema"] = {"$ref": "#/components/schemas/Nope"}; refuse(d, "ref")
    d = base(); d["operations"][0]["responses"]["200"]["schema"] = {"$ref": "http://x/y"}; refuse(d, "ref")
    d = base(); d["schemas"]["Pet"]["schema"]["properties"]["parent"] = {"$ref": "#/components/schemas/Pet"}; refuse(d, "recurs")
    d = base()
    d["schemas"]["A"] = {"source_ref": "a", "schema": {"type": "object", "properties": {"b": {"$ref": "#/components/schemas/B"}}}}
    d["schemas"]["B"] = {"source_ref": "b", "schema": {"type": "object", "properties": {"a": {"$ref": "#/components/schemas/A"}}}}
    refuse(d, "recurs")
    d = base(); d["schemas"]["Pet"]["schema"]["properties"]["x"] = {"$ref": "#/components/schemas/NewPet", "type": "object"}; refuse(d, "ref")


def test_non_dag_shared_refs_allowed():
    d = base()
    d["schemas"]["Pair"] = {"source_ref": "p", "schema": {"type": "object", "properties": {
        "a": {"$ref": "#/components/schemas/Pet"}, "b": {"$ref": "#/components/schemas/Pet"}}}}
    generate_openapi(d)


@pytest.mark.parametrize("kw", ["oneOf", "anyOf", "allOf", "not", "patternProperties", "if", "$defs", "discriminator", "additionalProperties_schema"])
def test_unsupported_complex_keywords_refuse(kw):
    d = base()
    s = d["schemas"]["Pet"]["schema"]["properties"]["tag"]
    if kw == "additionalProperties_schema":
        d["schemas"]["Pet"]["schema"]["additionalProperties"] = {"type": "string"}
    else:
        s[kw] = [{"type": "string"}]
    refuse(d, "unsupported|unknown")


def test_unknown_keys_types_methods_refuse():
    d = base(); d["schemas"]["Pet"]["schema"]["properties"]["x"] = {"type": "null"}; refuse(d, "type")
    d = base(); d["schemas"]["Pet"]["schema"]["properties"]["x"] = {"type": ["string", "null"]}; refuse(d, "type")
    d = base(); d["schemas"]["Pet"]["schema"]["properties"]["x"] = {"type": "string", "format": "weird"}; refuse(d, "unsupported|unknown")
    d = base(); d["operations"][0]["method"] = "trace"; refuse(d, "method")
    d = base(); d["operations"][0]["method"] = "GET "; refuse(d, "method")
    d = base(); d["operations"][0]["extra"] = 1; refuse(d, "unknown")
    d = base(); d["bogus"] = 1; refuse(d, "unknown")
    d = base(); d["operations"][0]["responses"] = {}; refuse(d, "response")
    d = base(); d["operations"][0]["responses"] = {"20": {"description": "x"}}; refuse(d, "status")
    d = base(); d["operations"][0]["responses"] = {"200": {}}; refuse(d, "description")
    d = base(); d["operations"][0]["parameters"][1]["in"] = "cookie"; refuse(d, "in")
    d = base(); d["operations"][0]["request_body"] = {"required": True, "schema": {"type": "string"}}; refuse(d, "body")
    d = base(); d["schemas"]["Pet"]["schema"]["required"] = ["nope"]; refuse(d, "required")
    d = base(); d["schemas"]["Pet"]["schema"]["required"] = ["id", "id"]; refuse(d, "required")
    d = base(); d["schemas"]["bad name!"] = d["schemas"]["Pet"]; refuse(d, "name")
    d = base(); d["schemas"]["Pet"]["schema"]["properties"]["x"] = {"type": "array"}; refuse(d, "items")
    d = base(); d["schemas"]["Pet"]["schema"]["properties"]["x"] = {"type": "string", "enum": []}; refuse(d, "enum")
    d = base(); d["schemas"]["Pet"]["schema"]["properties"]["x"] = {"type": "string", "minLength": 5, "maxLength": 2}; refuse(d, "length")
    d = base(); d["schemas"]["Pet"]["schema"]["properties"]["x"] = {"type": "integer", "minimum": 5, "maximum": 2}; refuse(d, "minimum")


def test_non_dict_inputs_refuse():
    for bad in (None, [], "x", 5):
        refuse(bad)
    d = base(); d["operations"] = {}; refuse(d, "operations")
    d = base(); d["operations"] = []; refuse(d, "operations")
    d = base(); d["info"]["title"] = ""; refuse(d, "title")
    d = base(); d["info"]["version"] = 1; refuse(d, "version")


# ---- examples ----
@pytest.mark.parametrize("ex", [{"id": "7", "name": "Rex"}, {"id": True, "name": "Rex"}, {"id": 1.5, "name": "Rex"},
                                {"id": 1}, {"id": 1, "name": "R", "unknown": 1}, {"id": 0, "name": "Rex"},
                                {"id": 1, "name": ""}, {"id": 1, "name": "x" * 41}, {"id": 1, "name": "Rex", "labels": [1]},
                                {"id": 1, "name": "Rex", "alive": 1}, [1]])
def test_incompatible_examples_refuse(ex):
    d = base(); d["operations"][0]["responses"]["200"]["example"] = ex; refuse(d, "example")


def test_example_numeric_edge_cases():
    d = base(); d["operations"][0]["responses"]["200"]["example"] = {"id": 1, "name": "R", "score": 3}
    generate_openapi(d)  # integer is a valid number
    for v in (float("nan"), float("inf"), True):
        d = base(); d["operations"][0]["responses"]["200"]["example"] = {"id": 1, "name": "R", "score": v}; refuse(d, "example|finite")
    d = base(); d["operations"][0]["responses"]["200"]["example"] = {"id": 2 ** 53 + 1, "name": "R"}; generate_openapi(d)
    d = base(); d["operations"][0]["responses"]["200"]["example"] = {"id": 1, "name": "R", "score": 1e999}; refuse(d, "example|finite")


def test_parameter_example_type_checked():
    d = base(); d["operations"][0]["parameters"][0]["example"] = "seven"; refuse(d, "example")
    d = base(); d["operations"][0]["parameters"][1]["example"] = "yes"; refuse(d, "example")


def test_example_without_schema_refuses():
    d = base(); d["operations"][0]["responses"]["404"]["example"] = {"a": 1}; refuse(d, "example")


def test_nullable_enum_and_enum_membership():
    d = base()
    d["schemas"]["Pet"]["schema"]["properties"]["kind"] = {"type": "string", "enum": ["cat", "dog"], "nullable": True}
    d["operations"][0]["responses"]["200"]["example"] = {"id": 1, "name": "R", "kind": None}
    r = generate_openapi(d)
    kind = r["openapi"]["components"]["schemas"]["Pet"]["properties"]["kind"]
    assert kind["type"] == ["string", "null"] and kind["enum"] == ["cat", "dog", None]
    d["operations"][0]["responses"]["200"]["example"] = {"id": 1, "name": "R", "kind": "cow"}
    refuse(d, "example")
    d = base(); d["schemas"]["Pet"]["schema"]["properties"]["kind"] = {"type": "string", "enum": ["a", 1]}; refuse(d, "enum")
    d = base(); d["schemas"]["Pet"]["schema"]["properties"]["kind"] = {"type": "string", "enum": ["a", "a"]}; refuse(d, "enum")


# ---- bounds N / N+1 ----
def _op(i):
    return {"operation_id": f"op{i}", "method": "get", "path": f"/p{i}", "summary": "s", "source_ref": f"r{i}",
            "responses": {"200": {"description": "ok"}}}


def test_operation_count_bound():
    n = 64
    d = base(); d["operations"] = [_op(i) for i in range(n)]; generate_openapi(d)
    d["operations"].append(_op(n)); refuse(d, "operations")


def test_schema_count_bound():
    n = 64
    d = base(); d["operations"] = [_op(0)]; d["schemas"] = {f"S{i}": {"source_ref": "r", "schema": {"type": "string"}} for i in range(n)}; generate_openapi(d)
    d["schemas"]["Extra"] = {"source_ref": "r", "schema": {"type": "string"}}; refuse(d, "schemas")


def test_property_count_bound():
    n = 64
    d = base(); d["operations"] = [_op(0)]; d["schemas"] = {"W": {"source_ref": "r", "schema": {"type": "object", "properties": {f"p{i}": {"type": "string"} for i in range(n)}}}}
    generate_openapi(d)
    d["schemas"]["W"]["schema"]["properties"]["pX"] = {"type": "string"}; refuse(d, "properties")


def _nest(depth):
    s = {"type": "string"}
    for _ in range(depth):
        s = {"type": "array", "items": s}
    return s


def test_depth_bound():
    n = 8
    d = base(); d["operations"] = [_op(0)]; d["schemas"] = {"D": {"source_ref": "r", "schema": _nest(n)}}; generate_openapi(d)
    d["schemas"]["D"]["schema"] = _nest(n + 1); refuse(d, "depth")


def test_deep_example_and_hostile_nesting_do_not_crash():
    d = base()
    x = []
    for _ in range(5000):
        x = [x]
    d["operations"][0]["responses"]["200"]["example"] = x
    refuse(d, "example|depth|bound")
    s = {"type": "string"}
    for _ in range(5000):
        s = {"type": "array", "items": s}
    d = base(); d["schemas"]["Pet"]["schema"]["properties"]["x"] = s
    refuse(d, "depth")


def test_parameter_and_response_count_bounds():
    n = 16
    d = base(); op = _op(0)
    op["parameters"] = [{"name": f"q{i}", "in": "query", "schema": {"type": "string"}} for i in range(n)]
    d["operations"] = [op]; generate_openapi(d)
    op["parameters"].append({"name": "qX", "in": "query", "schema": {"type": "string"}}); refuse(d, "parameters")
    m = 8
    d = base(); op = _op(0); op["responses"] = {str(200 + i): {"description": "d"} for i in range(m)}
    d["operations"] = [op]; generate_openapi(d)
    op["responses"][str(200 + m)] = {"description": "d"}; refuse(d, "responses")


def test_string_length_bounds():
    n = 500
    d = base(); d["operations"][0]["summary"] = "x" * n; generate_openapi(d)
    d["operations"][0]["summary"] = "x" * (n + 1); refuse(d, "summary|length")
    m = 200
    d = base(); d["operations"] = [_op(0)]; d["operations"][0]["path"] = "/" + "a" * (m - 1); generate_openapi(d)
    d["operations"][0]["path"] = "/" + "a" * m; refuse(d, "path")
    d = base(); d["operations"][0]["responses"]["200"]["example"] = {"id": 1, "name": "R", "tag": "x" * (1000 * 1000)}; refuse(d, "example|bound")


def test_example_node_bound():
    n = 1000
    d = base()
    d["schemas"]["Pet"]["schema"]["properties"]["labels"] = {"type": "array", "items": {"type": "string"}}
    ex = {"id": 1, "name": "R", "labels": ["a"] * (n - 4)}  # object(1)+id+name+labels(1)+items
    d["operations"][0]["responses"]["200"]["example"] = ex
    generate_openapi(d)
    ex["labels"].append("a"); refuse(d, "example|bound")


def test_nonfinite_and_boolean_bounds_in_schema():
    for k, v in (("minimum", float("nan")), ("maximum", float("inf")), ("minimum", True), ("minimum", "1")):
        d = base(); d["schemas"]["Pet"]["schema"]["properties"]["id"][k] = v; refuse(d, "minimum|maximum|finite|numeric")
    for v in (True, -1, 1.5, "3"):
        d = base(); d["schemas"]["Pet"]["schema"]["properties"]["name"]["maxLength"] = v; refuse(d, "length")


def test_input_not_mutated_and_no_aliasing():
    d = base(); snap = copy.deepcopy(d)
    r = generate_openapi(d)
    assert d == snap
    r["openapi"]["info"]["title"] = "changed"
    assert d["info"]["title"] == "Pets"


def test_sensitive_to_input_not_hardcoded():
    d = base(); d["operations"][0]["path"] = "/animals/{petId}"
    assert "/animals/{petId}" in generate_openapi(d)["openapi"]["paths"]
    d = base(); d["schemas"]["Pet"]["schema"]["properties"]["extra"] = {"type": "number"}
    assert "extra" in generate_openapi(d)["openapi"]["components"]["schemas"]["Pet"]["properties"]


def test_get_with_body_refused_and_unused_schema_listed():
    d = base(); d["operations"][0]["request_body"] = {"required": False, "schema": {"type": "string"}}; refuse(d, "body")
    d = base(); d["operations"][0]["request_body"] = {"required": False, "schema": {"$ref": "#/components/schemas/NewPet"}}; refuse(d, "body")


# =====================================================================
# R2: documented bounds pinned with literal numbers (N accepted, N+1 refused)
# =====================================================================
def test_documented_bound_constants_match_contract():
    assert (mod.MAX_OPERATIONS, mod.MAX_SCHEMAS, mod.MAX_PROPERTIES, mod.MAX_DEPTH) == (64, 64, 64, 8)
    assert (mod.MAX_PARAMETERS, mod.MAX_RESPONSES, mod.MAX_ENUM, mod.MAX_TEXT) == (16, 8, 32, 500)
    assert (mod.MAX_PATH, mod.MAX_EXAMPLE_NODES, mod.MAX_EXAMPLE_STRING) == (200, 1000, 2000)
    assert (mod.MAX_INPUT_BYTES, mod.MAX_INPUT_NODES, mod.MAX_RAW_DEPTH, mod.MAX_OUTPUT_BYTES) == (262144, 50000, 48, 1000000)


def _with_extra(**extra):
    d = base()
    d.update(extra)
    return d


def _nested_list(depth):
    x = []
    for _ in range(depth - 1):
        x = [x]
    return x


def test_input_depth_bound_48_vs_49():
    # key 'x' is unknown, so an input that passes the prescan fails later with 'unknown key'
    # (value of x sits at depth 1; a list nested k levels deep reaches depth k)
    with pytest.raises(ValueError, match="unknown key 'x'"):
        generate_openapi(_with_extra(x=_nested_list(48)))
    with pytest.raises(ValueError) as e:
        generate_openapi(_with_extra(x=_nested_list(49)))
    assert str(e.value) == "input depth bound exceeded"


def test_input_node_bound_50000_vs_50001():
    # count the nodes of the base request independently, then pad a list under unknown key 'x'
    def count(v):
        c, st = 0, [v]
        while st:
            y = st.pop(); c += 1
            if isinstance(y, list): st.extend(y)
            elif isinstance(y, dict): st.extend(y.values())
        return c
    b = count(base())
    # adding key x contributes the list node itself plus its items
    with pytest.raises(ValueError, match="unknown key 'x'"):
        generate_openapi(_with_extra(x=[0] * (50000 - b - 1)))
    with pytest.raises(ValueError) as e:
        generate_openapi(_with_extra(x=[0] * (50000 - b)))
    assert str(e.value) == "input node bound exceeded"


def test_input_byte_bound_262144_vs_262145():
    import json as _j
    d = _with_extra(x="")
    pad = 262144 - len(_j.dumps(d))
    d["x"] = "a" * pad
    assert len(_j.dumps(d)) == 262144
    with pytest.raises(ValueError, match="unknown key 'x'"):
        generate_openapi(d)
    d["x"] = "a" * (pad + 1)
    with pytest.raises(ValueError) as e:
        generate_openapi(d)
    assert str(e.value) == "input size bound exceeded (262144 bytes)"


def test_input_byte_bound_accepts_valid_request_at_limit():
    import json as _j
    d = base()
    d["schemas"]["Pet"]["schema"]["properties"]["kind"] = {"type": "string", "enum": [""]}
    pad = 262144 - len(_j.dumps(d))
    d["schemas"]["Pet"]["schema"]["properties"]["kind"]["enum"] = ["k" * pad]
    assert len(_j.dumps(d)) == 262144
    r = generate_openapi(d)
    assert len(r["canonical_json"]) > 262144 - 1000
    d["schemas"]["Pet"]["schema"]["properties"]["kind"]["enum"] = ["k" * (pad + 1)]
    refuse(d, "^input size bound exceeded")


def test_integer_64_bit_bound():
    for ok in (2 ** 63, 2 ** 64 - 1, -(2 ** 64 - 1), 0):
        with pytest.raises(ValueError, match="unknown key 'x'"):
            generate_openapi(_with_extra(x=ok))
    for bad in (2 ** 64, -(2 ** 64)):
        with pytest.raises(ValueError) as e:
            generate_openapi(_with_extra(x=bad))
        assert str(e.value) == "integer exceeds 64-bit bound"


def test_output_byte_bound_exact(monkeypatch):
    r = generate_openapi(base())
    n = len(r["canonical_json"])
    monkeypatch.setattr(mod, "MAX_OUTPUT_BYTES", n)
    assert generate_openapi(base())["canonical_json"] == r["canonical_json"]  # N accepted
    monkeypatch.setattr(mod, "MAX_OUTPUT_BYTES", n - 1)
    with pytest.raises(ValueError) as e:
        generate_openapi(base())
    assert str(e.value) == f"output size bound exceeded ({n - 1} bytes)"


def test_json_dumps_contract_spy(monkeypatch):
    import json as _j
    calls = []
    real = _j.dumps

    def spy(*a, **k):
        calls.append(k)
        return real(*a, **k)
    monkeypatch.setattr(mod.json, "dumps", spy)
    generate_openapi(base())
    assert any(k.get("allow_nan") is False and len(k) == 1 for k in calls)          # prescan size
    canon = [k for k in calls if k.get("sort_keys") is True and k.get("separators") == (",", ":")]
    assert canon and canon[0].get("ensure_ascii") is True and canon[0].get("allow_nan") is False
    assert any(k == {"sort_keys": True} for k in calls)                            # client example copy


def test_ascii_canonical_json_with_non_ascii_text():
    d = base()
    d["info"]["description"] = "caf\u00e9 \u2603 \U0001f600"
    r = generate_openapi(d)
    assert r["canonical_json"].isascii()
    assert "\\u00e9" in r["canonical_json"] and "\\u2603" in r["canonical_json"] and "\\ud83d\\ude00" in r["canonical_json"]
    assert r["openapi"]["info"]["description"] == d["info"]["description"]
    assert json.loads(r["canonical_json"]) == r["openapi"]
    assert r["sha256"] == hashlib.sha256(r["canonical_json"].encode("ascii")).hexdigest()


def test_object_count_and_text_bounds_literal():
    # 64 / 65 for operations, schemas, properties, parameters, responses (literals)
    d = base(); d["operations"] = [_op(i) for i in range(64)]; generate_openapi(d)
    d["operations"].append(_op(64)); refuse(d, "^operations exceed 64$")
    d = base(); d["operations"] = [_op(0)]
    d["schemas"] = {f"S{i}": {"source_ref": "r", "schema": {"type": "string"}} for i in range(64)}; generate_openapi(d)
    d["schemas"]["S64"] = {"source_ref": "r", "schema": {"type": "string"}}; refuse(d, "^schemas exceed 64$")
    d = base(); d["operations"] = [_op(0)]
    d["schemas"] = {"W": {"source_ref": "r", "schema": {"type": "object", "properties": {f"p{i}": {"type": "string"} for i in range(64)}}}}
    generate_openapi(d)
    d["schemas"]["W"]["schema"]["properties"]["p64"] = {"type": "string"}; refuse(d, "properties exceed 64$")
    d = base(); op = _op(0); op["parameters"] = [{"name": f"q{i}", "in": "query", "schema": {"type": "string"}} for i in range(16)]
    d["operations"] = [op]; generate_openapi(d)
    op["parameters"].append({"name": "q16", "in": "query", "schema": {"type": "string"}}); refuse(d, "parameters exceed 16$")
    d = base(); op = _op(0); op["responses"] = {str(200 + i): {"description": "d"} for i in range(8)}
    d["operations"] = [op]; generate_openapi(d)
    op["responses"]["208"] = {"description": "d"}; refuse(d, "responses exceed 8$")


@pytest.mark.parametrize("setter", [
    lambda d, v: d["info"].__setitem__("title", v),
    lambda d, v: d["info"].__setitem__("description", v),
    lambda d, v: d["operations"][0].__setitem__("summary", v),
    lambda d, v: d["operations"][0]["responses"]["404"].__setitem__("description", v),
    lambda d, v: d["operations"][0]["parameters"][0].__setitem__("description", v),
    lambda d, v: d["schemas"]["Pet"]["schema"].__setitem__("description", v),
])
def test_text_bound_500_vs_501(setter):
    d = base(); setter(d, "x" * 500); generate_openapi(d)
    d = base(); setter(d, "x" * 501); refuse(d, "500 characters")


def test_path_length_bound_200_vs_201():
    d = base(); d["operations"] = [_op(0)]; d["operations"][0]["path"] = "/" + "a" * 199; generate_openapi(d)
    d["operations"][0]["path"] = "/" + "a" * 200
    assert msg_of(d) == "path must start with '/' and be at most 200 characters"


def msg_of(d):
    with pytest.raises(ValueError) as e:
        generate_openapi(d)
    return str(e.value)


def test_example_node_bound_1000_vs_1001_exact_messages():
    d = base()
    d["operations"][0]["responses"]["200"]["example"] = {"id": 1, "name": "R", "labels": ["a"] * 996}  # 4 + 996 = 1000
    generate_openapi(d)
    d["operations"][0]["responses"]["200"]["example"]["labels"].append("a")
    assert msg_of(d) == "example exceeds 1000 nodes (bound)"


def test_example_string_bound_2000_vs_2001():
    d = base(); d["operations"][0]["responses"]["200"]["example"] = {"id": 1, "name": "R", "tag": "t" * 2000}
    generate_openapi(d)
    d["operations"][0]["responses"]["200"]["example"]["tag"] = "t" * 2001
    assert msg_of(d) == "example string exceeds bound"


def test_schema_depth_8_vs_9_arrays_and_objects():
    def objs(n):
        s = {"type": "string"}
        for _ in range(n):
            s = {"type": "object", "properties": {"c": s}}
        return s
    d = base(); d["operations"] = [_op(0)]; d["schemas"] = {"D": {"source_ref": "r", "schema": _nest(8)}}; generate_openapi(d)
    d["schemas"]["D"]["schema"] = _nest(9)
    assert msg_of(d).startswith("schema 'D'.items.items") and msg_of(d).endswith("schema depth bound 8 exceeded")
    d = base(); d["operations"] = [_op(0)]; d["schemas"] = {"D": {"source_ref": "r", "schema": objs(8)}}; generate_openapi(d)
    d["schemas"]["D"]["schema"] = objs(9)
    assert msg_of(d).endswith("schema depth bound 8 exceeded")


def test_enum_count_32_vs_33_and_value_bounds():
    d = base(); d["schemas"]["Pet"]["schema"]["properties"]["k"] = {"type": "string", "enum": [f"v{i}" for i in range(32)]}
    generate_openapi(d)
    d["schemas"]["Pet"]["schema"]["properties"]["k"]["enum"].append("v32")
    assert msg_of(d) == "schema 'Pet'.k: enum exceeds 32 values"


def test_length_keyword_bounds_literal():
    def with_len(k, v):
        d = base(); d["operations"] = [_op(0)]
        d["schemas"] = {"W": {"source_ref": "r", "schema": {"type": "string", k: v}}}
        return d
    for k in ("minLength", "maxLength"):
        for v in (0, 10000):
            generate_openapi(with_len(k, v))
        for v in (10001, -1, True, 1.5, "3", None):
            assert msg_of(with_len(k, v)) == f"schema 'W': {k} length must be an integer in 0..10000"


def test_identifier_length_bounds_64_vs_65():
    for field in ("schema", "operation_id", "param", "property"):
        d = base(); d["operations"] = [_op(0)]
        if field == "schema":
            d["schemas"] = {"a" * 64: {"source_ref": "r", "schema": {"type": "string"}}}
        elif field == "operation_id":
            d["operations"][0]["operation_id"] = "a" * 64
        elif field == "param":
            d["operations"][0]["parameters"] = [{"name": "a" * 64, "in": "query", "schema": {"type": "string"}}]
        else:
            d["schemas"] = {"W": {"source_ref": "r", "schema": {"type": "object", "properties": {"a" * 64: {"type": "string"}}}}}
        generate_openapi(d)
        if field == "schema":
            d["schemas"] = {"a" * 65: {"source_ref": "r", "schema": {"type": "string"}}}
        elif field == "operation_id":
            d["operations"][0]["operation_id"] = "a" * 65
        elif field == "param":
            d["operations"][0]["parameters"][0]["name"] = "a" * 65
        else:
            d["schemas"]["W"]["schema"]["properties"] = {"a" * 65: {"type": "string"}}
        refuse(d, "invalid|name")


# ---------- numeric / length boundary semantics ----------
def test_length_bounds_exact_in_examples():
    d = base()  # name: minLength 1 maxLength 40
    for n, ok in ((1, True), (40, True), (0, False), (41, False)):
        d["operations"][0]["responses"]["200"]["example"] = {"id": 1, "name": "n" * n}
        if ok:
            generate_openapi(d)
        else:
            refuse(d, "string length out of bounds")


def test_numeric_bounds_exact_in_examples():
    d = base(); d["schemas"]["Pet"]["schema"]["properties"]["id"] = {"type": "integer", "minimum": 1, "maximum": 10}
    for v, ok in ((1, True), (10, True), (0, False), (11, False)):
        d["operations"][0]["responses"]["200"]["example"] = {"id": v, "name": "R"}
        if ok:
            generate_openapi(d)
        else:
            refuse(d, "number out of bounds")
    d["schemas"]["Pet"]["schema"]["properties"]["score"] = {"type": "number", "minimum": "1/2" and 0.5, "maximum": 2.5}
    for v, ok in ((0.5, True), (2.5, True), (0.49, False), (2.51, False)):
        d["operations"][0]["responses"]["200"]["example"] = {"id": 1, "name": "R", "score": v}
        if ok:
            generate_openapi(d)
        else:
            refuse(d, "number out of bounds")


def test_schema_bound_pairs_equal_accepted_inverted_refused():
    d = base(); d["schemas"]["Pet"]["schema"]["properties"]["name"].update(minLength=3, maxLength=3)
    d["operations"][1]["request_body"]["example"] = {"name": "abc"}
    generate_openapi(d)
    d["schemas"]["Pet"]["schema"]["properties"]["name"].update(minLength=4)
    assert msg_of(d) == "schema 'Pet'.name: minLength exceeds maxLength (length bounds inverted)"
    d = base(); d["schemas"]["Pet"]["schema"]["properties"]["id"].update(minimum=5, maximum=5)
    d["operations"][0]["responses"]["200"]["example"] = {"id": 5, "name": "R"}
    d["operations"][1]["responses"]["201"]["example"] = {"id": 5, "name": "R"}
    generate_openapi(d)
    d["schemas"]["Pet"]["schema"]["properties"]["id"].update(minimum=6)
    assert msg_of(d) == "schema 'Pet'.id: minimum exceeds maximum"


def test_numeric_keyword_types_integer_vs_number():
    d = base(); d["schemas"]["Pet"]["schema"]["properties"]["id"]["minimum"] = 1.5
    refuse(d, "minimum must be a finite numeric value")
    d = base(); d["schemas"]["Pet"]["schema"]["properties"]["id"]["minimum"] = 1.0
    refuse(d, "minimum must be a finite numeric value")
    d = base(); d["schemas"]["Pet"]["schema"]["properties"]["score"].update(minimum=1.5, maximum=3)
    generate_openapi(d)
    d = base(); d["schemas"]["Pet"]["schema"]["properties"]["score"]["minimum"] = True
    refuse(d, "minimum must be a finite numeric value")
    d = base(); d["schemas"]["Pet"]["schema"]["properties"]["id"]["maximum"] = False
    refuse(d, "maximum must be a finite numeric value")
    d = base(); d["schemas"]["Pet"]["schema"]["properties"]["name"]["minimum"] = 1
    refuse(d, "unsupported or unknown schema keyword 'minimum'")
    d = base(); d["schemas"]["Pet"]["schema"]["properties"]["id"]["minLength"] = 1
    refuse(d, "unsupported or unknown schema keyword 'minLength'")


def test_isnum_and_matches_scalar_direct():
    assert mod._isnum(1) and mod._isnum(1.5) and mod._isnum(-3) and mod._isnum(0)
    for bad in (True, False, float("nan"), float("inf"), "1", None, [1], 1 + 0j):
        assert not mod._isnum(bad)
    assert mod._matches_scalar("x", "string") and not mod._matches_scalar(1, "string")
    assert mod._matches_scalar(True, "boolean") and not mod._matches_scalar(1, "boolean")
    assert mod._matches_scalar(1, "integer") and not mod._matches_scalar(True, "integer") and not mod._matches_scalar(1.0, "integer")
    assert mod._matches_scalar(1.5, "number") and mod._matches_scalar(2, "number") and not mod._matches_scalar(True, "number")
    for t in ("array", "object", "null", "nope"):
        assert mod._matches_scalar("x", t) is False
        assert mod._matches_scalar([], t) is False


def test_resolve_root_chain_bound_64_vs_65():
    def chain(n):
        comps = {f"S{i}": {"$ref": f"#/components/schemas/S{i + 1}"} for i in range(n)}
        comps[f"S{n}"] = {"type": "object"}
        return comps
    # chain(n) needs n+1 hops from the outer ref: 64 hops accepted, 65 refused
    assert mod._resolve_root({"$ref": "#/components/schemas/S0"}, chain(62))["type"] == "object"
    assert mod._resolve_root({"$ref": "#/components/schemas/S0"}, chain(63))["type"] == "object"
    with pytest.raises(ValueError, match="recursive"):
        mod._resolve_root({"$ref": "#/components/schemas/S0"}, chain(64))
    with pytest.raises(ValueError, match="recursive"):
        mod._resolve_root({"$ref": "#/components/schemas/A"}, {"A": {"$ref": "#/components/schemas/A"}})


# ---------- enum semantics ----------
@pytest.mark.parametrize("t,vals", [("number", [1, 1.0]), ("number", [1.5, 1.5]), ("integer", [1, 1]), ("boolean", [True, True]),
                                    ("string", ["a", "a"]), ("number", [2, 2.0, 3])])
def test_enum_duplicates_refused(t, vals):
    d = base(); d["schemas"]["Pet"]["schema"]["properties"]["k"] = {"type": t, "enum": vals}
    assert msg_of(d) == "schema 'Pet'.k: enum duplicate value"


@pytest.mark.parametrize("t,vals", [("number", [1, 2.5]), ("integer", [1, 2]), ("boolean", [True, False]),
                                    ("string", ["a", "A"]), ("number", [0, 0.5])])
def test_enum_distinct_values_accepted(t, vals):
    d = base(); d["schemas"]["Pet"]["schema"]["properties"]["k"] = {"type": t, "enum": vals}
    out = generate_openapi(d)["openapi"]["components"]["schemas"]["Pet"]["properties"]["k"]["enum"]
    assert out == vals


@pytest.mark.parametrize("t,vals", [("integer", [1.0]), ("integer", [True]), ("number", [True]), ("boolean", [1]),
                                    ("string", [1]), ("number", ["1"]), ("integer", [None])])
def test_enum_member_type_mismatch_refused(t, vals):
    d = base(); d["schemas"]["Pet"]["schema"]["properties"]["k"] = {"type": t, "enum": vals}
    assert msg_of(d) == f"schema 'Pet'.k: enum value type does not match {t}"


@pytest.mark.parametrize("t,enum,ex,ok", [
    ("string", ["cat", "dog"], "cat", True), ("string", ["cat", "dog"], "dog", True), ("string", ["cat", "dog"], "cow", False),
    ("string", ["cat"], 1, False),
    ("integer", [1, 2], 1, True), ("integer", [1, 2], 2, True), ("integer", [1, 2], 3, False),
    ("integer", [1], 1.0, False), ("integer", [1], True, False), ("integer", [0], False, False),
    ("number", [1.5, 2], 2.0, True), ("number", [1.5, 2], 1.5, True), ("number", [1.5, 2], 2, True), ("number", [1.5, 2], 1.6, False),
    ("number", [1], True, False), ("number", [0], False, False),
    ("boolean", [True], True, True), ("boolean", [True], False, False), ("boolean", [False], False, True), ("boolean", [True], 1, False),
    ("boolean", [False], 0, False),
])
def test_enum_example_membership(t, enum, ex, ok):
    d = base(); d["schemas"]["Pet"]["schema"]["properties"]["k"] = {"type": t, "enum": enum}
    d["operations"][0]["responses"]["200"]["example"] = {"id": 1, "name": "R", "k": ex}
    if ok:
        generate_openapi(d)
    else:
        refuse(d, "example")


def test_enum_none_semantics():
    d = base(); d["schemas"]["Pet"]["schema"]["properties"]["k"] = {"type": "string", "enum": ["a"]}
    d["operations"][0]["responses"]["200"]["example"] = {"id": 1, "name": "R", "k": None}
    assert msg_of(d) == "example operation 'getPet' response 200.k: null not allowed (not nullable)"
    d["schemas"]["Pet"]["schema"]["properties"]["k"]["nullable"] = True
    generate_openapi(d)
    d["operations"][0]["responses"]["200"]["example"]["k"] = "b"
    refuse(d, "value not in enum")
    d["operations"][0]["responses"]["200"]["example"]["k"] = "a"
    generate_openapi(d)


# ---------- paths ----------
def test_path_validation_exact():
    ok = ["/", "/a", "/a/b", "/a/{x}", "/a/{x}/b/{y_2}", "/a-b/c.d/e_f~g"]
    for p in ok:
        d = base(); d["operations"] = [_op(0)]; d["operations"][0]["path"] = p
        holders = [x[1:-1] for x in p.split("/") if x.startswith("{")]
        d["operations"][0]["parameters"] = [{"name": h, "in": "path", "required": True, "schema": {"type": "string"}} for h in holders]
        generate_openapi(d)
    for bad in (5, None, ["/a"], "a", "", "/a/", "//a", "/a//b", "/a b", "/a/{x", "/a/x}", "/{}", "/{1a}", "/a{x}", "/{x}{y}", "/a?x"):
        d = base(); d["operations"] = [_op(0)]; d["operations"][0]["path"] = bad
        with pytest.raises(ValueError, match="path"):
            generate_openapi(d)


def test_same_path_different_methods_ok_equivalent_templates_refused():
    d = base(); d["operations"] = []
    for i, m in enumerate(("get", "put", "delete", "patch")):
        o = _op(i); o["method"] = m; o["path"] = "/same"; d["operations"].append(o)
    generate_openapi(d)
    d = base(); d["operations"] = []
    for i, (p, name) in enumerate((("/a/{x}/b", "x"), ("/a/{y}/c", "y"))):
        o = _op(i); o["path"] = p
        o["parameters"] = [{"name": name, "in": "path", "required": True, "schema": {"type": "string"}}]
        d["operations"].append(o)
    generate_openapi(d)
    d["operations"][1]["path"] = "/a/{y}/b"
    assert msg_of(d) == "duplicate equivalent path templates '/a/{x}/b' and '/a/{y}/b'"
    d["operations"][1]["path"] = "/a/{x}/b"; d["operations"][1]["parameters"][0]["name"] = "x"
    assert msg_of(d) == "duplicate method/path GET /a/{x}/b"


# ---------- required / operation_id / parameter name ----------
def test_required_list_shape_refused():
    for bad in ("id", None, 5, {"id": 1}, [1], [None], ["id", 1]):
        d = base(); d["schemas"]["Pet"]["schema"]["required"] = bad
        assert msg_of(d) == "schema 'Pet': required must be a list of property names"


def test_operation_id_validation():
    for bad in ("1abc", "a-b", "a b", "", None, 5, "a.b", "é"):
        d = base(); d["operations"][0]["operation_id"] = bad
        assert msg_of(d) == "operation 0: invalid operation_id"
    for good in ("_a", "A1_b", "a"):
        d = base(); d["operations"][0]["operation_id"] = good; generate_openapi(d)


def test_parameter_name_validation():
    for bad in ("bad name", "", None, 5, "a/b", "é"):
        d = base(); d["operations"][0]["parameters"][1]["name"] = bad
        assert msg_of(d) == "operation 'getPet' parameter 1: invalid name"
    for good in ("a.b", "a-b", "A_1"):
        d = base(); d["operations"][0]["parameters"][1]["name"] = good; generate_openapi(d)


def test_header_reserved_names_and_case_rules():
    for nm in ("Accept", "content-type", "AUTHORIZATION"):
        d = base(); d["operations"][0]["parameters"].append({"name": nm, "in": "header", "schema": {"type": "string"}})
        assert msg_of(d) == "operation 'getPet' parameter 2: reserved header name"
        for loc in ("query",):  # reserved names are fine outside headers
            d = base(); d["operations"][0]["parameters"].append({"name": nm, "in": loc, "schema": {"type": "string"}})
            generate_openapi(d)
    d = base(); d["operations"][0]["parameters"].append({"name": "X-Trace", "in": "header", "schema": {"type": "string"}})
    generate_openapi(d)
    # headers are case-insensitive duplicates; query names are case-sensitive; same name in different locations is fine
    d = base(); d["operations"][0]["parameters"] += [{"name": "X-Id", "in": "header", "schema": {"type": "string"}},
                                                     {"name": "x-id", "in": "header", "schema": {"type": "string"}}]
    assert msg_of(d) == "operation 'getPet': duplicate parameter header:x-id"
    d = base(); d["operations"][0]["parameters"] += [{"name": "q", "in": "query", "schema": {"type": "string"}},
                                                     {"name": "Q", "in": "query", "schema": {"type": "string"}},
                                                     {"name": "petId", "in": "header", "schema": {"type": "string"}}]
    generate_openapi(d)
    d = base(); d["operations"][0]["parameters"].append({"name": "verbose", "in": "query", "schema": {"type": "string"}})
    assert msg_of(d) == "operation 'getPet': duplicate parameter query:verbose"


def test_parameter_required_flag_rules():
    d = base(); d["operations"][0]["parameters"][1]["required"] = 1
    assert msg_of(d) == "operation 'getPet' parameter 1: required must be boolean"
    d = base(); d["operations"][0]["parameters"][0]["required"] = 1
    assert msg_of(d) == "operation 'getPet' parameter 0: required must be boolean"
    d = base(); del d["operations"][0]["parameters"][0]["required"]
    assert msg_of(d) == "operation 'getPet' parameter 0: path parameter must declare required true"
    d = base(); d["operations"][0]["parameters"][1].pop("required", None)
    assert generate_openapi(d)["openapi"]["paths"]["/pets/{petId}"]["get"]["parameters"][1]["required"] is False
    d = base(); d["operations"][0]["parameters"][1]["required"] = True
    assert generate_openapi(d)["openapi"]["paths"]["/pets/{petId}"]["get"]["parameters"][1]["required"] is True


# ---------- parameter schema rules ----------
def test_parameter_schema_ref_refused():
    for loc in ("query", "header"):
        d = base(); d["operations"][0]["parameters"].append(
            {"name": "z", "in": loc, "schema": {"$ref": "#/components/schemas/Pet"}})
        assert msg_of(d) == "operation 'getPet' parameter 2 schema: $ref not allowed here"
    d = base(); d["operations"][0]["parameters"][0]["schema"] = {"$ref": "#/components/schemas/Pet"}
    assert msg_of(d) == "operation 'getPet' parameter 0 schema: $ref not allowed here"


def test_parameter_schema_scalar_and_array_rules():
    def put(loc, schema, name="z"):
        d = base()
        d["operations"][0]["parameters"].append({"name": name, "in": loc, "schema": schema})
        return d
    for loc in ("query", "header"):
        for good in ({"type": "string"}, {"type": "integer"}, {"type": "boolean", "nullable": True},
                     {"type": "array", "items": {"type": "string"}}, {"type": "array", "items": {"type": "integer"}},
                     {"type": "array", "items": {"type": "boolean"}}, {"type": "array", "items": {"type": "number"}}):
            generate_openapi(put(loc, good))
        for bad in ({"type": "object"}, {"type": "array", "items": {"type": "array", "items": {"type": "string"}}},
                    {"type": "array", "items": {"type": "object"}}, {"type": "array", "items": {"$ref": "#/components/schemas/Pet"}},
                    {"type": "array", "items": {"type": "string", "nullable": True}}):
            assert msg_of(put(loc, bad)) == "operation 'getPet' parameter 2: parameter schema must be scalar or array of scalars"
    for bad in ({"type": "array", "items": {"type": "string"}}, {"type": "object"}):
        d = base(); d["operations"][0]["parameters"][0]["schema"] = bad
        assert msg_of(d) == "operation 'getPet' parameter 0: parameter schema must be scalar"
    d = base(); d["operations"][0]["parameters"][0]["schema"] = {"type": "integer", "nullable": True}
    assert msg_of(d) == "operation 'getPet' parameter 0: path parameter cannot be nullable"
    d = base(); d["operations"][0]["parameters"][0]["schema"] = {"type": "string", "enum": ["a"]}; d["operations"][0]["parameters"][0]["example"] = "a"
    generate_openapi(d)


# ---------- request body ----------
def test_request_body_required_default_and_flags():
    d = base(); del d["operations"][1]["request_body"]["required"]
    assert generate_openapi(d)["openapi"]["paths"]["/pets"]["post"]["requestBody"]["required"] is False
    d = base(); d["operations"][1]["request_body"]["required"] = True
    assert generate_openapi(d)["openapi"]["paths"]["/pets"]["post"]["requestBody"]["required"] is True
    d = base(); d["operations"][1]["request_body"]["required"] = False
    assert generate_openapi(d)["openapi"]["paths"]["/pets"]["post"]["requestBody"]["required"] is False
    d = base(); d["operations"][1]["request_body"]["required"] = "yes"
    assert msg_of(d) == "operation 'createPet': request_body required must be boolean"
    d = base(); d["operations"][1]["request_body"]["schema"] = {"type": "array", "items": {"type": "string"}}
    del d["operations"][1]["request_body"]["example"]
    assert msg_of(d) == "operation 'createPet': request body schema must be an object"
    for m in ("put", "patch"):
        d = base(); d["operations"][1]["method"] = m; generate_openapi(d)
    for m in ("get", "delete"):
        d = base(); d["operations"][1]["method"] = m
        assert msg_of(d) == f"operation 'createPet': {m} operations cannot have a request body"


def test_request_body_alias_ref_to_object_ok_and_scalar_alias_refused():
    d = base()
    d["schemas"]["Alias"] = {"source_ref": "a", "schema": {"$ref": "#/components/schemas/NewPet"}}
    d["operations"][1]["request_body"]["schema"] = {"$ref": "#/components/schemas/Alias"}
    generate_openapi(d)
    d["schemas"]["Str"] = {"source_ref": "s", "schema": {"type": "string"}}
    d["schemas"]["Alias"]["schema"] = {"$ref": "#/components/schemas/Str"}
    del d["operations"][1]["request_body"]["example"]
    refuse(d, "request body schema must be an object")


# ---------- recursion detection ----------
def _ref(n):
    return {"$ref": f"#/components/schemas/{n}"}


def _graph(edges, names=None):
    d = base(); d["operations"] = [_op(0)]; d["schemas"] = {}
    nodes = set(edges) | {t for v in edges.values() for t in v} | set(names or ())
    for n in sorted(nodes):
        props = {f"p{i}": _ref(t) for i, t in enumerate(edges.get(n, []))}
        d["schemas"][n] = {"source_ref": "r", "schema": {"type": "object", "properties": props}}
    return d


@pytest.mark.parametrize("edges", [
    {"A": ["A"]}, {"A": ["B"], "B": ["A"]}, {"A": ["B"], "B": ["C"], "C": ["A"]},
    {"A": ["B"], "B": ["C"], "C": ["B"]},              # cycle not containing the DFS start
    {"A": ["C"], "B": ["C"], "C": ["D"], "D": ["C"]},  # cycle reached after a finished node
    {"Q": ["A"], "A": ["B"], "B": ["Q"]},               # start is not alphabetically first
    {"A": ["B", "C"], "B": ["D"], "C": ["D"], "D": ["A"]},  # diamond that closes a loop
])
def test_cycles_refused(edges):
    assert "recursive $ref cycle involving" in msg_of(_graph(edges))


@pytest.mark.parametrize("edges", [
    {"A": ["B", "C"], "B": ["D"], "C": ["D"]},   # diamond (shared child reached twice, not a cycle)
    {"S1": ["S3"], "S2": ["S3"]},                   # shared leaf reached from two DFS roots
    {"A": ["B"], "B": ["C"], "C": ["D"], "D": ["E"]},  # chain
    {"A": ["B", "B2"], "B": ["C"], "B2": ["C"], "C": ["D"], "E": ["D"]},
])
def test_dags_accepted(edges):
    generate_openapi(_graph(edges))


def test_cycle_message_names_node_and_dangling_ref_message():
    assert msg_of(_graph({"A": ["B"], "B": ["A"]})) in ("recursive $ref cycle involving 'A'", "recursive $ref cycle involving 'B'")
    d = _graph({"A": ["B"]}); del d["schemas"]["B"]
    assert msg_of(d) == "dangling $ref to 'B' in schema 'A'"


# ---------- output ordering ----------
def test_parameter_order_path_query_header_then_name():
    d = base(); op = _op(0); op["path"] = "/x/{b}/{a}"
    op["parameters"] = [
        {"name": "hz", "in": "header", "schema": {"type": "string"}}, {"name": "ha", "in": "header", "schema": {"type": "string"}},
        {"name": "qz", "in": "query", "schema": {"type": "string"}}, {"name": "qa", "in": "query", "schema": {"type": "string"}},
        {"name": "b", "in": "path", "required": True, "schema": {"type": "string"}},
        {"name": "a", "in": "path", "required": True, "schema": {"type": "string"}}]
    d["operations"] = [op]
    got = [(p["in"], p["name"]) for p in generate_openapi(d)["openapi"]["paths"]["/x/{b}/{a}"]["get"]["parameters"]]
    assert got == [("path", "a"), ("path", "b"), ("query", "qa"), ("query", "qz"), ("header", "ha"), ("header", "hz")]


def _ex_fixture():
    d = base(); d["operations"] = []
    for oid, path in (("zeta", "/z"), ("alpha", "/a")):
        o = {"operation_id": oid, "method": "post", "path": path + "/{k}/{j}", "summary": "s", "source_ref": "s",
             "parameters": [{"name": "k", "in": "path", "required": True, "schema": {"type": "string"}, "example": "1"},
                            {"name": "j", "in": "path", "required": True, "schema": {"type": "string"}, "example": "2"}],
             "request_body": {"schema": {"$ref": "#/components/schemas/NewPet"}, "example": {"name": "n"}},
             "responses": {"404": {"description": "x", "schema": {"type": "string"}, "example": "nope"},
                           "200": {"description": "x", "schema": {"type": "string"}, "example": "ok"}}}
        d["operations"].append(o)
    return d


def test_client_examples_order_and_key_order():
    r = generate_openapi(_ex_fixture())
    got = [(e["operation_id"], e["kind"], e.get("name") or e.get("status") or "") for e in r["client_examples"]]
    assert got == [("alpha", "parameter", "j"), ("alpha", "parameter", "k"), ("alpha", "request", ""),
                   ("alpha", "response", "200"), ("alpha", "response", "404"),
                   ("zeta", "parameter", "j"), ("zeta", "parameter", "k"), ("zeta", "request", ""),
                   ("zeta", "response", "200"), ("zeta", "response", "404")]
    for e in r["client_examples"]:
        assert list(e) == sorted(e)  # keys serialized sorted


def test_source_trace_tiebreak_order():
    d = base()
    d["schemas"]["Pet"]["source_ref"] = "same"; d["schemas"]["NewPet"]["source_ref"] = "same"
    d["operations"][0]["source_ref"] = "same"; d["operations"][1]["source_ref"] = "same"
    tr = generate_openapi(d)["source_trace"]
    assert [(t["kind"], t["name"]) for t in tr] == [("operation", "createPet"), ("operation", "getPet"),
                                                    ("schema", "NewPet"), ("schema", "Pet")]
    d["operations"][1]["source_ref"] = "aaa"
    assert generate_openapi(d)["source_trace"][0] == {"kind": "operation", "name": "createPet", "source_ref": "aaa"}


def test_response_status_forms():
    d = base(); d["operations"][0]["responses"] = {"default": {"description": "d"}, "100": {"description": "d"}, "599": {"description": "d"}}
    generate_openapi(d)
    for bad in ("600", "099", "2000", "2xx", "20", "", "default "):
        d = base(); d["operations"][0]["responses"] = {bad: {"description": "d"}}
        with pytest.raises(ValueError, match="status"):
            generate_openapi(d)


def test_parameter_order_location_beats_name():
    d = base(); op = _op(0); op["path"] = "/x/{zp}"
    op["parameters"] = [{"name": "ah", "in": "header", "schema": {"type": "string"}},
                        {"name": "aq", "in": "query", "schema": {"type": "string"}},
                        {"name": "zp", "in": "path", "required": True, "schema": {"type": "string"}}]
    d["operations"] = [op]
    got = [(p["in"], p["name"]) for p in generate_openapi(d)["openapi"]["paths"]["/x/{zp}"]["get"]["parameters"]]
    assert got == [("path", "zp"), ("query", "aq"), ("header", "ah")]


def test_nullable_object_and_array_of_object_parameters_refused():
    for bad in ({"type": "object", "nullable": True},
                {"type": "array", "items": {"type": "object"}, "nullable": True},
                {"type": "array", "items": {"type": "array", "items": {"type": "string"}}, "nullable": True}):
        d = base(); d["operations"][0]["parameters"].append({"name": "z", "in": "query", "schema": bad})
        assert msg_of(d) == "operation 'getPet' parameter 2: parameter schema must be scalar or array of scalars"
    d = base(); d["operations"][0]["parameters"].append(
        {"name": "z", "in": "query", "schema": {"type": "array", "items": {"type": "string"}, "nullable": True}, "example": ["a"]})
    generate_openapi(d)


def test_inline_body_and_response_schema_depth_8_vs_9():
    def objs(n):
        s = {"type": "string"}
        for _ in range(n):
            s = {"type": "object", "properties": {"c": s}}
        return s
    d = base(); d["operations"][1]["request_body"] = {"required": True, "schema": objs(8)}
    generate_openapi(d)
    d["operations"][1]["request_body"]["schema"] = objs(9)
    assert msg_of(d).endswith(": schema depth bound 8 exceeded")
    d = base(); d["operations"][0]["responses"]["200"] = {"description": "d", "schema": _nest(8)}
    generate_openapi(d)
    d["operations"][0]["responses"]["200"]["schema"] = _nest(9)
    assert "schema depth bound 8 exceeded" in msg_of(d)


# ---------- R3 pins ----------
def test_cycle_message_names_exact_node():
    assert msg_of(_graph({"A": ["B"], "B": ["A"]})) == "recursive $ref cycle involving 'A'"
    assert msg_of(_graph({"B": ["C"], "C": ["B"]}, names=["A"])) == "recursive $ref cycle involving 'B'"
    assert msg_of(_graph({"A": ["A"]})) == "recursive $ref cycle involving 'A'"


def test_parameter_schema_depth_8_reaches_scalar_check_9_hits_depth_bound():
    d = base(); d["operations"][0]["parameters"].append({"name": "z", "in": "query", "schema": _nest(8)})
    assert msg_of(d) == "operation 'getPet' parameter 2: parameter schema must be scalar or array of scalars"
    d = base(); d["operations"][0]["parameters"].append({"name": "z", "in": "query", "schema": _nest(9)})
    m = msg_of(d)
    assert m == "operation 'getPet' parameter 2 schema" + ".items" * 8 + ": schema depth bound 8 exceeded"
