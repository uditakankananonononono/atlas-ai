"""Error-coding repair pins for app/core/depth_quality.py (cl1260r2).

SOURCE repair (shared core): quality_envelope now validates that
required_inputs/evidence/assumptions/limitations are non-string Sequences
and that evidence entries are Mappings, raising ValueError instead of
escaping raw TypeError/AttributeError on junk. Found through m12
legal_support's envelope (assumptions junk escaped on every method);
the same class is live for clinical_support, m20 legal_support, education
and m16 finance callers - this core fix closes it for all of them without
touching their files. Byte-identical proof: the 100-case legal_support
golden battery from cl1260r (captured at base 94fe792d) re-pinned here.
String sequence arguments keep their pre-existing behavior (iterated as
characters) - only previously-crashing inputs change.
"""
import hashlib
import json
import pytest
from app.core.depth_quality import attach_quality, quality_envelope
from app.modules.m12_ai_research_lab.legal_support import legal_support, LEGAL_METHODS, ROW_IDS

GOLD_PINS = json.loads(r'''{"legal_support_sha256_pins": {"access_to_justice__noisy": "dfd3aba32b0720204f683e1d858fb96ee04a2203951ba9ca2d0d26b153b96c04", "access_to_justice__valid": "ae77b8112866184f8c4107236d93ed39315d24842052ccc95ebdf6b34797bce5", "administrative_law__noisy": "95b78fde2ebf68237fba7752ee05158b5060b702e081708b878b036e7ccfabac", "administrative_law__valid": "8f7f55b9c42ce7e3c7bbd5a51e9f1a1d5aa244dbebf0871f383318849ffb6bf4", "agency_proceedings__noisy": "39f193ba7fae046499445d976dcfd2a009ba203582afc4d242a13c9236904689", "agency_proceedings__valid": "0aa630c818650b2b75991ad83f375c4cc598153a132d1498e416e5de4bb2d0d2", "alternative_fee_arrangements__noisy": "2c9887309d523c557ddbb06521b1750ad604cde7e3dc58aa9af4a59fa123fc70", "alternative_fee_arrangements__valid": "6f077f79143094de29dc544fa49d7d8d44b39638a4ac7ba49621b7c6c24088b7", "appellate_practice__noisy": "6fd1db3576c24a86860263b66660f2dd2133ab21dd5ac9314a49e82c79109622", "appellate_practice__valid": "1ddcf606865e226a66276f31bd3c90b3164fb3c73b02c058169c049bd32f2ed2", "arbitration__noisy": "b76d7db116783700124d83985f7154da6fb7bc3c463b54293726ec96c1611427", "arbitration__valid": "e8534f7a86736951b7f2976c802937bba8782501ea2c3e59d705fb805266cc6e", "attorney_client_privilege__noisy": "6449dd75ac13eaa0ac7df1d58ddaed6bffdfccb824f601df6249a4ddbd741ea7", "attorney_client_privilege__valid": "39d5bcb8506adce5a7adec5bafbc79b64e9f9856ed6c5c24e96a005ca54f446d", "brief_writing__noisy": "5ef032e311e57b0b233cdff18b97f2f79eee9dca0e054543744ea79ce04bd52a", "brief_writing__valid": "bdc35ac707b9620ab78dc8ed7acc5ab297245461bc308ee65d460a54fa4d0a2e", "conflicts_of_interest__noisy": "620f16da44ef34836fd0f0cfaea9c8ea7e316924ecd202095ba9797a41ed0706", "conflicts_of_interest__valid": "540d30b42e45591fdab19208464aba9d300a49eb269ad6b2dab67861facaaca3", "constitutional_law__noisy": "1998e512a32158c0ff8a1514b31e721f9110243dcb342096ce56302915d97332", "constitutional_law__valid": "0e89bf2483be8ac706d6228ab5b617c6bb9ad2ab15df3300f8259a062a5b3b56", "criminal_appeals__noisy": "5709de46e2ed2a57d5a7805d4247c4648a3a0d3940cdff6362024e12756d5306", "criminal_appeals__valid": "0e48a61d29dad7c8d51d7ba2a7075586b74ebb0a87a75b5d3f045817b2c94ced", "depositions__noisy": "79f4076bb67914d0cbdd7dbbd30c7fbd3e22082c87ecfb627034cbf505650dda", "depositions__valid": "b08522912ca3abbfccf120bdfc256dfb683f57bd9a75dac29ba8364d325de6b5", "discovery__noisy": "479d67ea5247d5597cca45e0653c8695c319e1ef07b1a3d191012f973559b6f0", "discovery__valid": "0e469c585fbd2ccffce616cf276a1c01af6bd5939b08893e776c2c0395bc7d1f", "dispute_resolution__noisy": "d4e9b77f4dc01f6528b6470b601d9b3db2a5874f8e6c9c1c657119aa5ececc7e", "dispute_resolution__valid": "dd671ab00cc6389d99cef2d76aa62d6d860282ab839b6094ec74dfe1bb5c1ea4", "document_review__noisy": "148e6b29aaf8383747d67de45e8695fb226e78bf012967d6c821830a709879eb", "document_review__valid": "7eb2395ebcfd62e6d16f00252b7f1ac8d444b8d1f477c971465b2275ff3b6129", "due_process__noisy": "13f8892a0452298866ba9c13099de43d7f563b3d2699f81dd50ca6938f8b2907", "due_process__valid": "93c04ea2bc476eaf14cc79691f6cace56ae05d8601fd1914963ad3499a039b8a", "e_discovery__noisy": "51a7dd543d720cac4499afd3e35e72abf248be65a41ff53adc8b1869ea500a0b", "e_discovery__valid": "b2fe7bf11a08e26f96664d71654f9df909a267da59ab8e8652e50fbdb350f08a", "equal_protection__noisy": "acd21c39e845812169b9fd199dc1c7d6f911ba1dec49fe52f18bda39221e3282", "equal_protection__valid": "4162b752b9a61e8d246c9c1d23b83ee0027fed7415f590a0d5b7030cbfc5996e", "evidence_analysis__noisy": "09be62ba1f4819e864c65a4f07e33c4a06b4e25b9e910c1207cfa777a57d9ec3", "evidence_analysis__valid": "1e6852d8f155d8e6d651efc1ce3aceeffcad9751d9c957ef591ef7bde3fe880a", "first_amendment__noisy": "8f7eba6d8f527cfd7254e63a88a4f92b401d060f93e3e7c12050ec67d02e71bc", "first_amendment__valid": "d9202528ada9ce1cf1d6f536e762b3f4dfd419002017de175b32c3431f044f26", "fourth_amendment__noisy": "b41de0a30b503f2a156936a2783b3456fe9fff0edfb2d83d947fc3f698433b76", "fourth_amendment__valid": "fc0ffff817d072c571d018af93197680dbfebb10ea5344fdc0caa127eb1b40a7", "human_rights__noisy": "0ddf7ed281b6de9f50b8a68c40d894857e70538bc6033542aa3bebb6d08c35ff", "human_rights__valid": "f1f86a15f5a9f3262a6e14fa9bedd96703db18e31a456d21184e6f028f762fa9", "international_law__noisy": "766d3813546842b4f260d5b05b23b39ce4773eb922cce3d7c0f769c702d97064", "international_law__valid": "c8798417496369c807cc5424245562470e17ad0a9f35e867aaa0d562e5228f6e", "international_trade__noisy": "c35f285ae1b08f236a0c51f3611aa65f95106da80cca69b88eaf4dbc02000a23", "international_trade__valid": "e92fd5d676d92409010fca2d882912c2bf0dddea137a05f73e8bbc7383471d41", "judicial_review__noisy": "2ad2e47f5ff37e592c999acb2941e3137f2b31045801cd54039b42012f1ee279", "judicial_review__valid": "88eca5b045872ff0476467415b4a44a2cd6e133608d1d33fa3d34a27424e11ed", "jury_selection__noisy": "aa8e1c92dc460ec8d15b36868fcaca6f0685b39e85da1a5586fa47fd8eccc170", "jury_selection__valid": "d7081dda5c10c244fd39c32eecd1dd6da5939d4ece25249eb68a4a28b5f498a6", "knowledge_management__noisy": "d638fd1a26a905ea94ed34be399e10d04d6abf699a595113c2fee5322554075f", "knowledge_management__valid": "5090a2f3ebc30b9719502e0000da08d589451915698b505b576745a111d5b336", "law_firm_management__noisy": "26fb03e806dc3f9339911026289fb81274bfeb4458084f1a65b5c98a9ff32327", "law_firm_management__valid": "17a3bfd34d3f57fe4775baf0155f0b9934167f3db73d70862a7c7fc4da2d9d8e", "legal_aid__noisy": "a956d633bbe0df3bb1dbb828faa416ebd82ca1dde2dcf5a39224bed72d5c046f", "legal_aid__valid": "17ba0228b869670002ccab9621d5f005f542a3878e8bce101b2dbb5a370860a7", "legal_analytics__noisy": "8f5f1e03d8276665df04440f69db3c00ac302377c83adde68064f27e074853ab", "legal_analytics__valid": "6514721fc06e6afafa9b299b1b70512963dc11754d5531a26588841b6670a02a", "legal_billing__noisy": "ca02752a73a37cc4fd7667f5bc3f003d76bcdd713f3861c05b28b7cf48f61dfa", "legal_billing__valid": "d24a67ac3a82da26096da3604b5b0a70fb1b6b3c3eba1f152c363a6f64edf099", "legal_citations__noisy": "474981c679e69fe25a0f7b8bbe3e466b4af1260192c3a99aae6530e08ff84c9a", "legal_citations__valid": "78ab92f4d54143c60e1af6e3f4384857be31a9f474f4d9ebab5334960e6344be", "legal_education__noisy": "e1ee415bda43c1dc0ece7ef69f8904b6d9af6bc867cefc0b2e9cf929739491f0", "legal_education__valid": "3747e3d2ea860612c547034098eac0c5e9353534fa0a7cff29a3c9df1ccabd73", "legal_ethics__noisy": "a906df30689727f8c99be0d5b52b4dc772baa7e8b777bb5555d43f46d59aeade", "legal_ethics__valid": "8268d3f539a128366eb2b56f6ccfe1cbdaedb887bb8262b2a66237fe9945c13e", "legal_malpractice__noisy": "eec37a4538f846c0a3946a8d4244cb4120419cb381de49fbbf971a3f95cb380c", "legal_malpractice__valid": "2c7572e22cb856820f893ccf7c0ea1cb5f809cb001483e417dcadd2e7fe9192e", "legal_operations__noisy": "1c518a303a51a2cdd16be3fc18866cc9a7a4020a32265784713e313401305993", "legal_operations__valid": "4e617d9776e3b8c5b8916c354c18e1c51f1df184a19459eaa7de36a95e1b5407", "legal_project_management__noisy": "24125f0318ffbdea784864f93acefa99593ecf4c45e83493a1da4c3743ec3ac8", "legal_project_management__valid": "ca67f53e7f53c9a2a938ccb2d08491a6edf0003a5d1e4c830fe33f097e706d91", "legal_technology__noisy": "35a6122fad7a23d32fdb3ed91538ee0c8870675fadbfed4e09ea159a7aca515a", "legal_technology__valid": "225f25119f77ba30153b28241613cfe7fe1c5c5d11183635b07374361336aef6", "legal_writing__noisy": "a9e7a430be6e3642b05d09fe319b6f9126a5b878343c1496312855528e2631bd", "legal_writing__valid": "47590f7c2ffd279cd137eea1b2a9942c26351c016db33bda8ae06467fa536573", "litigation_strategy__noisy": "2fcb8ad21b9ef2ba4c913afabb9700d03f644fe1411e75c2e3764bdbabec8344", "litigation_strategy__valid": "75fe61884ac66909c6344e095d8758a9f0473507354258b3515158021a48acc2", "mediation__noisy": "b7c3a1d2b1e01bcdb5e988c6e6b6400ad4f986c5cdabc258cf28f9800086e49d", "mediation__valid": "771cc06aa81f34adc0e805f863ebbb63908219d9e2e310ab3b813d6d55ffc19c", "oral_argument__noisy": "7a26bf00cd273b6649f3694fcb1d08e3f8c02059a059bd7a1ada0e0ddb37a571", "oral_argument__valid": "359bfd21f1cf6ad8a6f4f261fdd96d6eea40f219602ab3e258c7968e83f49f3d", "predictive_coding__noisy": "9a427ed182ce543bc0c3e483dcb4fed83115676e3c67f9892e94844c48b809ec", "predictive_coding__valid": "543523732e5caee069a3cb249d404a53b56d40b694d1403735cacdeb0af5056e", "pro_bono_practice__noisy": "b67d9012bee34b1b71ad727490f3bccba688df2ab83bfd14e7a2fd997eed4877", "pro_bono_practice__valid": "d68ea172144280ec2a0d00a9e80ff72989d6e240ab592507ac43bf89273d54e9", "professional_responsibility__noisy": "b1984df2158126cabd2d8c457a1486486bfa9b0530468d78a2e1545173284f36", "professional_responsibility__valid": "4b9dad7335a00a22ff44ae43db54637384dbcd7d3083b389faaa4a002854aaf7", "regulatory_practice__noisy": "4f12d9f3d994d3a256573a528d58de86a0f4f32281186bd4a43688d5252f17c2", "regulatory_practice__valid": "e3ebb88e0c747c5603f07c1c4910d275626fcd979f4d60e1f128d6f8f92412c8", "sentencing_guidelines__noisy": "005a55bdac7742af3ebcc0660bff35988e5c6ac27eab09d625abea010abd9fe9", "sentencing_guidelines__valid": "001e8b38c08f06b516bf2400ad9850fa2649f5f755fc6debd0f2d2e6df8181e6", "treaties__noisy": "bc8521a7c24fd522efea2a5ab40645dd8f5b6603068b9ff24965da7f4de7159b", "treaties__valid": "717a66788de02f63783891d46f17bfcd866d11214222112be195f1534ff44a68", "trial_preparation__noisy": "42978c1719c798d673361dd42ee01050685ed486f9acc28686ce79cde77cf09c", "trial_preparation__valid": "54d139114ede6e278c42c30d502d99689600e574a94e00de5a1a47b07e207985", "witness_preparation__noisy": "7c9a706b30c4a220f23525a00576e715e33b247e4fcb17dfa37df09a279a6c3d", "witness_preparation__valid": "2c11129906b7dec7a90a82afd367e808fc57e19708e976038bbc2ab4c0061b0f"}}''')["legal_support_sha256_pins"]

AUTH = {"title": "Controlling source", "citation": "X 1", "source_url": "https://law.example/x",
        "authority_type": "primary", "jurisdiction": "J", "last_checked_at": "2026-09-21",
        "holding_or_rule": "supplied rule"}
BASE = {"jurisdiction": "J", "as_of": "2026-09-21"}

def payload(method):
    d = dict(BASE)
    if method in {"sentencing_guidelines", "criminal_appeals", "constitutional_law", "first_amendment",
                  "fourth_amendment", "due_process", "equal_protection", "administrative_law",
                  "regulatory_practice", "agency_proceedings", "judicial_review", "international_law",
                  "treaties", "human_rights", "international_trade"}:
        d |= {"authorities": [AUTH, {**AUTH, "citation": "Y 2", "is_contrary": True}],
              "issues": [{"issue": "scope", "elements_or_standard": ["element"],
                          "facts_supporting": ["fact"], "missing_facts": [], "authority_citations": ["X 1"]}]}
    elif method in {"arbitration", "mediation", "dispute_resolution", "litigation_strategy", "discovery",
                    "depositions", "trial_preparation", "evidence_analysis", "witness_preparation",
                    "jury_selection", "appellate_practice", "legal_writing", "legal_citations",
                    "brief_writing", "oral_argument"}:
        d |= {"authorities": [AUTH], "objectives": ["preserve issue"],
              "tasks": [{"id": "t", "task": "review record", "evidence_refs": ["e1"]}]}
    elif method in {"legal_ethics", "professional_responsibility", "conflicts_of_interest",
                    "attorney_client_privilege", "legal_malpractice", "pro_bono_practice", "legal_aid",
                    "access_to_justice"}:
        d |= {"authorities": [AUTH], "parties": [{"id": "p"}], "facts": ["identity"],
              "duties": [{"duty": "loyalty", "required_facts": ["identity"]}]}
    elif method in {"legal_technology", "e_discovery", "legal_analytics", "predictive_coding", "document_review"}:
        d |= {"documents": [{"id": "d", "sha256": "abc", "labels": ["responsive"], "privilege_candidate": True}],
              "protocol": {"labels": ["responsive"]},
              "validation_set": {"true_positive": 8, "false_positive": 2, "false_negative": 2}}
    else:
        d |= {"matters": [{"id": "m", "budget": 100, "entries": [{"amount": 40}], "milestones": ["review"]}],
              "controls": ["approval"]}
    return d

def variants(method):
    return {"valid": payload(method),
            "noisy": payload(method) | {"extra_junk": [1, {"k": "v"}], "assumptions": ["a1"]}}

def canon(result):
    return hashlib.sha256(json.dumps(result, sort_keys=True, default=str).encode()).hexdigest()

@pytest.mark.parametrize("method", sorted(LEGAL_METHODS, key=lambda x: ROW_IDS[x]))
@pytest.mark.parametrize("variant", ["valid", "noisy"])
def test_legal_support_output_byte_identical(method, variant):
    key = f"{method}__{variant}"
    assert canon(legal_support(method, variants(method)[variant])) == GOLD_PINS[key]

# --- defect pins at the core envelope ---

ENV = dict(domain="legal", method="m", inputs={}, result={"row_id": 1})

@pytest.mark.parametrize("bad", [True, 0, 1.5, None])
def test_assumptions_non_sequence_coded(bad):
    with pytest.raises(ValueError, match="assumptions must be a sequence"):
        quality_envelope(**ENV, assumptions=bad)

@pytest.mark.parametrize("bad", [True, 0, None, [None], ["x"], [1.5], [[1]]])
def test_evidence_junk_coded(bad):
    with pytest.raises(ValueError, match="evidence"):
        quality_envelope(**ENV, evidence=bad if isinstance(bad, list) else [bad])

@pytest.mark.parametrize("field", ["required_inputs", "limitations"])
@pytest.mark.parametrize("bad", [True, 0, None])
def test_other_sequences_coded(field, bad):
    with pytest.raises(ValueError, match="must be a sequence"):
        quality_envelope(**ENV, **{field: bad})

def test_attach_quality_assumptions_coded():
    with pytest.raises(ValueError, match="assumptions must be a sequence"):
        attach_quality({"row_id": 1}, domain="legal", method="m", inputs={},
                       required_inputs=[], evidence=[], assumptions=True)

def test_valid_envelope_output_unchanged():
    out = quality_envelope(**ENV, required_inputs=["jurisdiction"], evidence=[AUTH],
                           assumptions=["a1"], limitations=["l1"])
    assert out["uncertainty"]["assumptions"] == ["a1"]
    assert out["limitations"] == ["l1"]
    assert out["evaluation"]["cited_evidence_items"] == 1

# --- end-to-end through legal_support: assumptions junk now coded ---

@pytest.mark.parametrize("bad", [True, 0, 1.5])
def test_legal_support_junk_assumptions_coded(bad):
    d = payload("legal_aid")
    d["assumptions"] = bad
    with pytest.raises(ValueError, match="assumptions must be a sequence"):
        legal_support("legal_aid", d)


def test_assumptions_mapping_accepted_as_base():
    # cl1260r3: base iterated mapping keys; cl1260r2 wrongly refused. Restored.
    out = quality_envelope(**ENV, assumptions={"a": 1})
    assert out["uncertainty"]["assumptions"] == ["a"]


def test_legal_support_assumptions_mapping_accepted_as_base():
    d = payload("legal_aid")
    d["assumptions"] = {"a": 1}
    out = legal_support("legal_aid", d)
    assert out["quality"]["uncertainty"]["assumptions"] == ["a"]


def test_string_sequences_keep_preexisting_char_behavior():
    out = quality_envelope(**ENV, assumptions="ab", limitations="")
    assert out["uncertainty"]["assumptions"] == ["a", "b"]
    assert out["limitations"] == []


# --- cl1260r3 pins: the Sequence gate must not reject previously-accepted ---
# inputs.  Pre-image output hashes computed on the base (94fe792d) module.

def _canon(o):
    return hashlib.sha256(json.dumps(o, sort_keys=True, default=str).encode()).hexdigest()


def test_preserved_empty_mapping_and_sets_byte_identical():
    out = quality_envelope(domain="legal", method="m", inputs={}, result={"x": 1},
                           evidence={}, assumptions=set(), limitations=set(), required_inputs={})
    assert out["evaluation"]["evidence_items"] == 0
    assert _canon(out) == "cb2b0476b149ac6be2682960450eb9e2a0f1b524bd0ae9c7b4fad9b409e4b8ab"


def test_preserved_nonempty_set_assumptions_byte_identical():
    out = quality_envelope(domain="legal", method="m", inputs={"a": 1}, result={"x": 1},
                           required_inputs=["a"], evidence=[], assumptions={1, 2}, limitations=set())
    assert _canon(out) == "3fbdb94d9fdd5875440a0b950e13e46837a743bf24e433befee24603f334592c"


def test_preserved_generator_assumptions_byte_identical():
    out = quality_envelope(domain="clinical", method="m", inputs={"a": 1}, result={"x": 1},
                           required_inputs=["a"], evidence=[],
                           assumptions=(x for x in ["g1", "g2"]), limitations=())
    assert _canon(out) == "7c093d581390c67d404a8e60f95f528818f71d9d0133713b37494bdcde4da2d5"


def test_preserved_empty_generator_truthy_byte_identical():
    # a generator is always truthy: base reported "moderate" even when it was empty
    out = quality_envelope(domain="clinical", method="m", inputs={"a": 1}, result={"x": 1},
                           required_inputs=["a"], evidence=[], assumptions=(x for x in ()), limitations=())
    assert out["uncertainty"]["level"] == "moderate"
    assert _canon(out) == "61c4a4b3f088cfbae054b42757758af86bd0ac3bd7cf0fdd34b1ed1050cc0ea8"


def test_preserved_iterator_limitations_byte_identical():
    out = quality_envelope(domain="finance", method="m", inputs={"a": 1}, result={"x": 1},
                           required_inputs=("a",), evidence=(), limitations=iter(["l1"]))
    assert _canon(out) == "b2c325af577e27324939d82cdb4ff76071185e0393756581d6d4a4487964ac66"


def test_preserved_dict_required_inputs_byte_identical():
    out = quality_envelope(domain="education", method="m", inputs={"k1": 1, "k2": 2}, result={"x": 1},
                           required_inputs={"k1": 0, "k2": 0}, evidence=[], assumptions=[], limitations=[])
    assert out["evaluation"]["input_completeness"] == 1.0
    assert _canon(out) == "d14b4116f55fb4e40c37337cf5e7cb36fdb5dee9779da02eda5ea65c52010f26"


def test_preserved_str_sequence_args_byte_identical():
    out = quality_envelope(domain="legal", method="m", inputs={"a": 1}, result={"x": 1},
                           required_inputs="a", evidence=[], assumptions="xy", limitations="z")
    assert _canon(out) == "3ed09eccdc102c82985dc2e0b310bad2a67345477cfb41374812fa62cfed31d2"


def test_preserved_frozenset_args_byte_identical():
    out = quality_envelope(domain="legal", method="m", inputs={"a": 1}, result={"x": 1},
                           required_inputs=frozenset({"a"}), evidence=[],
                           assumptions=frozenset({"s"}), limitations=frozenset())
    assert _canon(out) == "fa12f9cf17f90f2ba8509d3984053be8610873ee5bff5797890194c1d93d3adb"


def test_preserved_duck_typed_evidence_byte_identical():
    class Getful:
        def __init__(self, d): self._d = d
        def get(self, k, default=None): return self._d.get(k, default)
    out = quality_envelope(domain="legal", method="m", inputs={"a": 1}, result={"x": 1},
                           required_inputs=["a"], evidence=[Getful({"citation": "c"})],
                           assumptions=[], limitations=[])
    assert out["evaluation"]["cited_evidence_items"] == 1
    assert _canon(out) == "1a87b41e919fde17a7bc89fbaee68aa350b82633c2f9db649d33a0c8c7d7581a"


def test_coded_method_none():
    with pytest.raises(ValueError):
        quality_envelope(domain="legal", method=None, inputs={}, result={"x": 1})


def test_coded_unhashable_domain():
    with pytest.raises(ValueError):
        quality_envelope(domain=[], method="m", inputs={}, result={"x": 1})


def test_coded_generator_evidence():
    # len() on a generator crashed raw on base; refusal is correct, but coded
    with pytest.raises(ValueError):
        quality_envelope(domain="legal", method="m", inputs={}, result={"x": 1},
                         evidence=(x for x in []))


def test_coded_str_evidence_entry():
    with pytest.raises(ValueError):
        quality_envelope(domain="legal", method="m", inputs={}, result={"x": 1}, evidence=["nope"])
