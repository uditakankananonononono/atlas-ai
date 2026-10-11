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
    n = mod.MAX_OPERATIONS
    d = base(); d["operations"] = [_op(i) for i in range(n)]; generate_openapi(d)
    d["operations"].append(_op(n)); refuse(d, "operations")


def test_schema_count_bound():
    n = mod.MAX_SCHEMAS
    d = base(); d["operations"] = [_op(0)]; d["schemas"] = {f"S{i}": {"source_ref": "r", "schema": {"type": "string"}} for i in range(n)}; generate_openapi(d)
    d["schemas"]["Extra"] = {"source_ref": "r", "schema": {"type": "string"}}; refuse(d, "schemas")


def test_property_count_bound():
    n = mod.MAX_PROPERTIES
    d = base(); d["operations"] = [_op(0)]; d["schemas"] = {"W": {"source_ref": "r", "schema": {"type": "object", "properties": {f"p{i}": {"type": "string"} for i in range(n)}}}}
    generate_openapi(d)
    d["schemas"]["W"]["schema"]["properties"]["pX"] = {"type": "string"}; refuse(d, "properties")


def _nest(depth):
    s = {"type": "string"}
    for _ in range(depth):
        s = {"type": "array", "items": s}
    return s


def test_depth_bound():
    n = mod.MAX_DEPTH
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
    n = mod.MAX_PARAMETERS
    d = base(); op = _op(0)
    op["parameters"] = [{"name": f"q{i}", "in": "query", "schema": {"type": "string"}} for i in range(n)]
    d["operations"] = [op]; generate_openapi(d)
    op["parameters"].append({"name": "qX", "in": "query", "schema": {"type": "string"}}); refuse(d, "parameters")
    m = mod.MAX_RESPONSES
    d = base(); op = _op(0); op["responses"] = {str(200 + i): {"description": "d"} for i in range(m)}
    d["operations"] = [op]; generate_openapi(d)
    op["responses"][str(200 + m)] = {"description": "d"}; refuse(d, "responses")


def test_string_length_bounds():
    n = mod.MAX_TEXT
    d = base(); d["operations"][0]["summary"] = "x" * n; generate_openapi(d)
    d["operations"][0]["summary"] = "x" * (n + 1); refuse(d, "summary|length")
    m = mod.MAX_PATH
    d = base(); d["operations"] = [_op(0)]; d["operations"][0]["path"] = "/" + "a" * (m - 1); generate_openapi(d)
    d["operations"][0]["path"] = "/" + "a" * m; refuse(d, "path")
    d = base(); d["operations"][0]["responses"]["200"]["example"] = {"id": 1, "name": "R", "tag": "x" * (mod.MAX_EXAMPLE_NODES * 1000)}; refuse(d, "example|bound")


def test_example_node_bound():
    n = mod.MAX_EXAMPLE_NODES
    d = base()
    d["schemas"]["Pet"]["schema"]["properties"]["labels"] = {"type": "array", "items": {"type": "string"}}
    ex = {"id": 1, "name": "R", "labels": ["a"] * (n - 4)}  # object(1)+id+name+labels(1)+items
    d["operations"][0]["responses"]["200"]["example"] = ex
    generate_openapi(d)
    ex["labels"].append("a"); refuse(d, "example|bound")


def test_total_input_size_bound():
    d = base(); d["info"]["title"] = "x" * (mod.MAX_TEXT)
    d["operations"] = []
    for i in range(mod.MAX_OPERATIONS):
        o = _op(i); o["summary"] = "y" * mod.MAX_TEXT
        d["operations"].append(o)
    d["schemas"] = {}
    r = None
    try:
        r = generate_openapi(d)
    except ValueError as e:
        assert "size" in str(e)
    if r is not None:
        assert len(r["canonical_json"]) <= mod.MAX_OUTPUT_BYTES


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
