"""Row704 traversal-boundary tests: preflight fence, strict builtin types, raw caps, no echo.

Hostile spies are subclasses of the builtin types whose every observable method records a call.
A spy must be refused by type before any method on it is invoked, so the call log stays empty.
"""
import pytest

from app.modules.m20_general_cognitive_worker import openapi704 as mod
from app.modules.m20_general_cognitive_worker.openapi704 import generate_openapi
from tests.modules.test_m20_api704_schema import base

MARK = "HOSTILE_MARK_7"
LOG = []


def _rec(name):
    def f(self, *a, **k):
        LOG.append(name)
        raise AssertionError("spy method called: " + name)
    return f


_NAMES = ("__iter__", "__len__", "__getitem__", "__contains__", "__eq__", "__ne__", "__hash__", "__repr__",
          "__str__", "__bool__", "__int__", "__index__", "__float__", "__lt__", "__gt__", "keys", "items",
          "values", "get", "__reversed__", "__format__", "__bit_length__", "bit_length", "strip",
          "startswith", "encode", "__add__", "__radd__")


def _spy(base_type):
    ns = {n: _rec(n) for n in _NAMES}
    return type("Spy" + base_type.__name__, (base_type,), ns)


SpyDict, SpyList, SpyStr, SpyInt, SpyFloat = (_spy(t) for t in (dict, list, str, int, float))


class SpyKey(str):
    """str subclass usable as a dict key (hash/eq untouched) whose other methods record calls."""
    for _n in ("__iter__", "__len__", "__repr__", "__str__", "strip", "startswith", "encode"):
        locals()[_n] = _rec(_n)
    del _n


@pytest.fixture(autouse=True)
def _clear():
    LOG.clear()
    yield


def _expect(d, msg):
    with pytest.raises(ValueError) as e:
        generate_openapi(d)
    assert str(e.value) == msg
    assert LOG == []


def _plain(sub, plain):
    """a spy that wraps real contents without calling any recorded method."""
    return sub(plain)


TYPE_MSG = "unsupported input value type"


def _placements():
    out = {}
    d = base(); out["root dict"] = _plain(SpyDict, d)
    d = base(); d["operations"] = _plain(SpyList, d["operations"]); out["operations list"] = d
    d = base(); d["operations"][0] = _plain(SpyDict, d["operations"][0]); out["operation dict"] = d
    d = base(); d["schemas"] = _plain(SpyDict, d["schemas"]); out["schemas dict"] = d
    d = base(); d["schemas"]["Pet"]["schema"] = _plain(SpyDict, d["schemas"]["Pet"]["schema"]); out["schema node"] = d
    d = base(); d["schemas"]["Pet"]["schema"]["required"] = _plain(SpyList, ["id", "name"]); out["required list"] = d
    d = base(); d["operations"][0]["responses"]["200"]["example"] = _plain(SpyDict, {"id": 7, "name": "Rex", "owner": None}); out["example dict"] = d
    d = base(); d["operations"][0]["parameters"][0]["example"] = SpyInt(7); out["example int"] = d
    d = base(); d["operations"][0]["parameters"][1]["example"] = SpyStr("x"); out["example str"] = d
    d = base(); d["schemas"]["Pet"]["schema"]["properties"]["score"] = {"type": "number", "minimum": SpyFloat(1.5)}; out["float spy"] = d
    d = base(); d["schemas"]["Pet"]["schema"]["properties"]["id"]["minimum"] = SpyInt(1); out["int spy"] = d
    d = base(); d["info"]["title"] = SpyStr("T"); out["title str"] = d
    d = base(); d["operations"][0]["method"] = SpyStr("get"); out["method str"] = d
    d = base(); d["schemas"]["Pet"]["schema"]["properties"]["id"]["enum"] = [SpyInt(1)]; out["enum int spy"] = d
    return out


@pytest.mark.parametrize("name", sorted(_placements()))
def test_subclass_anywhere_refused_without_touching_it(name):
    _expect(_placements()[name], TYPE_MSG)


def test_non_builtin_value_types_refused_by_constant_message():
    class Opaque:
        def __getattr__(self, n):
            LOG.append(n)
            raise AssertionError(n)

    for bad in (Opaque(), (1, 2), {1, 2}, b"x", bytearray(b"x"), 1 + 2j):
        d = base(); d["operations"][0]["parameters"][1]["example"] = bad
        _expect(d, TYPE_MSG)


def test_str_subclass_key_refused_without_touching_it():
    class K(str):
        pass
    for k in (K("zz"), K("qq")):
        d = base(); d[k] = 1
        _expect(d, "non-string key refused")
    d = base(); d["schemas"]["Pet"]["schema"]["properties"][SpyKey("tag2")] = {"type": "string"}
    _expect(d, "non-string key refused")


def test_non_str_key_message_has_no_type_name():
    d = base(); d[(1, 2)] = 1
    _expect(d, "non-string key refused")


def test_root_not_dict_still_refused_after_fence():
    for bad in ([], "x", 1, None):
        _expect(bad, "request must be an object")
    _expect(SpyList(), TYPE_MSG)


def test_fence_runs_before_any_validation_message():
    # a subclass hidden behind an otherwise-invalid request is reported by the fence, not by validation
    d = base(); d["bogus"] = SpyDict(); d["info"] = 5
    _expect(d, TYPE_MSG)


def test_container_counts_checked_before_iteration():
    # raw count cap on a list: 50000 total nodes; one over is refused with the node-bound message
    d = base(); d["x"] = [0] * 60000
    with pytest.raises(ValueError) as e:
        generate_openapi(d)
    assert str(e.value) == "input node bound exceeded"


def test_key_length_cap_500_vs_501():
    d = base(); d["schemas"]["Pet"]["schema"]["properties"]["tag"]["example_ignored"] = 1
    e = base(); e["x" * 500] = 1
    with pytest.raises(ValueError) as ex:
        generate_openapi(e)
    assert str(ex.value) == "unknown key in request"
    e = base(); e["x" * 501] = 1
    with pytest.raises(ValueError) as ex:
        generate_openapi(e)
    assert str(ex.value) == "input key exceeds bound"


def test_required_list_raw_cap_before_item_checks():
    d = base(); d["schemas"]["Pet"]["schema"]["required"] = ["id"] * 65
    with pytest.raises(ValueError) as e:
        generate_openapi(d)
    assert str(e.value) == "schema 'Pet': required exceeds 64"
    d["schemas"]["Pet"]["schema"]["required"] = [5] * 65
    with pytest.raises(ValueError) as e:
        generate_openapi(d)
    assert str(e.value) == "schema 'Pet': required exceeds 64"


# ---- no raw caller value is echoed
def _hostile_cases():
    cases = {}

    def put(name, fn):
        d = base(); fn(d); cases[name] = d
    put("top key", lambda d: d.update({MARK: 1}))
    put("info key", lambda d: d["info"].update({MARK: 1}))
    put("op key", lambda d: d["operations"][0].update({MARK: 1}))
    put("param key", lambda d: d["operations"][0]["parameters"][0].update({MARK: 1}))
    put("response key", lambda d: d["operations"][0]["responses"]["200"].update({MARK: 1}))
    put("schema entry key", lambda d: d["schemas"]["Pet"].update({MARK: 1}))
    put("schema keyword", lambda d: d["schemas"]["Pet"]["schema"]["properties"]["tag"].update({MARK: 1}))
    put("schema type", lambda d: d["schemas"]["Pet"]["schema"]["properties"]["tag"].update({"type": MARK}))
    put("property name", lambda d: d["schemas"]["Pet"]["schema"]["properties"].update({MARK + "!": {"type": "string"}}))
    put("schema name", lambda d: d["schemas"].update({MARK + "#": d["schemas"]["Pet"]}))
    put("status", lambda d: d["operations"][0]["responses"].update({MARK: {"description": "x"}}))
    put("path segment", lambda d: d["operations"][0].update({"path": "/" + MARK + "$"}))
    put("ref value", lambda d: d["schemas"]["Pet"]["schema"]["properties"].update({"r": {"$ref": MARK}}))
    put("example extra property", lambda d: d["operations"][0]["responses"]["200"].update({"example": {"id": 7, "name": "Rex", MARK: 1}}))
    put("example nested key", lambda d: d["operations"][1]["request_body"].update({"example": {"name": "Rex", MARK: [1]}}))
    put("method", lambda d: d["operations"][0].update({"method": MARK}))
    put("operation_id", lambda d: d["operations"][0].update({"operation_id": MARK + "-"}))
    put("param name", lambda d: d["operations"][0]["parameters"][1].update({"name": MARK + "!"}))
    put("param in", lambda d: d["operations"][0]["parameters"][1].update({"in": MARK}))
    return cases


@pytest.mark.parametrize("name", sorted(_hostile_cases()))
def test_refusal_message_never_echoes_caller_value(name):
    with pytest.raises(ValueError) as e:
        generate_openapi(_hostile_cases()[name])
    assert MARK not in str(e.value)
    assert "\n" not in str(e.value)


def test_unknown_key_messages_are_constant():
    for d, msg in ((_hostile_cases()["top key"], "unknown key in request"),
                   (_hostile_cases()["info key"], "unknown key in info"),
                   (_hostile_cases()["schema keyword"], "schema 'Pet'.tag: unsupported or unknown schema keyword for type string")):
        with pytest.raises(ValueError) as e:
            generate_openapi(d)
        assert str(e.value) == msg


def test_example_unexpected_property_message_constant():
    d = _hostile_cases()["example extra property"]
    with pytest.raises(ValueError) as e:
        generate_openapi(d)
    assert str(e.value) == "example operation 'getPet' response 200: unexpected property"


# ---- trailing-newline identifier fence ($ matches before a final newline; fullmatch must be used)
def _nl_cases():
    cases = {}

    def put(name, fn):
        d = base(); fn(d); cases[name] = d
    put("schema name", lambda d: d["schemas"].update({"Pet2\n": d["schemas"]["Pet"]}))
    put("property name", lambda d: d["schemas"]["Pet"]["schema"]["properties"].update({"zz\n": {"type": "string"}}))
    put("operation_id", lambda d: d["operations"][0].update({"operation_id": "getPet\n"}))
    put("path segment", lambda d: d["operations"][1].update({"path": "/pets2\n"}))
    put("status", lambda d: d["operations"][0]["responses"].update({"500\n": {"description": "x"}}))
    put("param name", lambda d: d["operations"][0]["parameters"][1].update({"name": "verbose\n"}))
    put("ref", lambda d: d["operations"][0]["responses"]["200"].update({"schema": {"$ref": "#/components/schemas/Pet\n"}}))
    return cases


@pytest.mark.parametrize("name", sorted(_nl_cases()))
def test_trailing_newline_identifiers_refused(name):
    with pytest.raises(ValueError) as e:
        generate_openapi(_nl_cases()[name])
    assert "\n" not in str(e.value)


def test_hostile_and_valid_inputs_leave_no_spy_calls():
    generate_openapi(base())
    assert LOG == []


def test_precheck_node_bound_exact_when_container_is_last_walked():
    # x is the first key, so it is walked last and the container pre-check sees the full count
    def count(v):
        c, st = 0, [v]
        while st:
            y = st.pop(); c += 1
            if type(y) is list: st.extend(y)
            elif type(y) is dict: st.extend(y.values())
        return c
    b = count(base())
    ok = {"x": [0] * (50000 - b - 1)}; ok.update(base())
    assert count(ok) == 50000
    with pytest.raises(ValueError) as e:
        generate_openapi(ok)
    assert str(e.value) == "unknown key in request"
    bad = {"x": [0] * (50000 - b)}; bad.update(base())
    with pytest.raises(ValueError) as e:
        generate_openapi(bad)
    assert str(e.value) == "input node bound exceeded"


def test_required_list_64_accepted_65_refused():
    d = base()
    names = ["p%d" % i for i in range(64)]
    d["schemas"]["Pet"]["schema"]["properties"] = {n: {"type": "string"} for n in names}
    d["schemas"]["Pet"]["schema"]["required"] = names
    d["operations"][0]["responses"]["200"]["example"] = {n: "v" for n in names}
    d["operations"][1]["responses"]["201"]["example"] = {n: "v" for n in names}
    generate_openapi(d)
    d["schemas"]["Pet"]["schema"]["required"] = names + ["p0"]
    with pytest.raises(ValueError) as e:
        generate_openapi(d)
    assert str(e.value) == "schema 'Pet': required exceeds 64"


def test_nullable_must_be_exact_boolean():
    for bad in (1, 0, "no", "true", None, 1.0, [], {}):
        d = base()
        d["schemas"]["Pet"]["schema"]["properties"]["tag"]["nullable"] = bad
        with pytest.raises(ValueError) as e:
            generate_openapi(d)
        assert str(e.value) == "schema 'Pet'.tag: nullable must be boolean"
    for ok in (True, False):
        d = base()
        d["schemas"]["Pet"]["schema"]["properties"]["tag"]["nullable"] = ok
        generate_openapi(d)


def _peak(request):
    import tracemalloc
    tracemalloc.start()
    try:
        with pytest.raises(ValueError) as e:
            generate_openapi(request)
        peak = tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()
    return str(e.value), peak


def test_prescan_wide_list_refused_before_extend_peak_under_1mb():
    d = base()
    d["x"] = [0] * 3_000_000
    msg, peak = _peak(d)
    assert msg == "input node bound exceeded"
    assert peak < 1_000_000


def test_prescan_wide_dict_refused_before_iteration_peak_under_1mb():
    d = base()
    d["x"] = {str(i): 0 for i in range(600_000)}
    msg, peak = _peak(d)
    assert msg == "input node bound exceeded"
    assert peak < 1_000_000


def test_integer_schema_refuses_float_example_even_when_integral():
    d = base()
    d["operations"][0]["parameters"][0]["example"] = 7.0
    with pytest.raises(ValueError) as e:
        generate_openapi(d)
    assert str(e.value) == "example operation 'getPet' parameter petId: expected integer"
