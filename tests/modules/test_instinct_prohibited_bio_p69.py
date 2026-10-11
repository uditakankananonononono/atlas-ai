"""P69|L58 prohibited-bio screen: hermetic stdlib unittest surface."""
import copy
import unittest

from app.modules.instinct_doc.prohibited_bio_p69 import (
    PROHIBITED_PATTERNS, screen, screen_batch)

DOCUMENTED_PATTERNS = (
    ('wet_lab_protocol', ('incubate at', 'centrifuge', 'pipette', 'culture medium', 'inoculate')),
    ('pathogen_enhancement', ('gain of function', 'enhance transmissibility', 'increase virulence')),
    ('harm_instruction', ('how to synthesize', 'how to culture', 'weaponiz')),
)


def doc(text, doc_id='d1', kind='protocol'):
    return {'id': doc_id, 'kind': kind, 'text': text}


class TestBlockedCategories(unittest.TestCase):
    def test_wet_lab_protocol_blocked_with_category_and_offset(self):
        out = screen(doc('We incubate at 37C overnight.'))
        self.assertEqual(out['verdict'], 'blocked:wet_lab_protocol')
        self.assertEqual(out['matched_pattern'], 'incubate at')
        self.assertEqual(out['offset'], 3)
        out = screen(doc('Samples were Centrifuged gently.'))
        self.assertEqual(out['verdict'], 'blocked:wet_lab_protocol')
        self.assertEqual(out['matched_pattern'], 'centrifuge')
        self.assertEqual(out['offset'], 13)
        out = screen(doc('Add the culture medium now.', kind='instruction'))
        self.assertEqual(out['verdict'], 'blocked:wet_lab_protocol')
        self.assertEqual(out['matched_pattern'], 'culture medium')

    def test_pathogen_enhancement_blocked(self):
        out = screen(doc('A gain of function study.', kind='claim'))
        self.assertEqual(out['verdict'], 'blocked:pathogen_enhancement')
        self.assertEqual(out['matched_pattern'], 'gain of function')
        self.assertEqual(out['offset'], 2)
        out = screen(doc('Aims to enhance transmissibility of the virus.'))
        self.assertEqual(out['verdict'], 'blocked:pathogen_enhancement')
        self.assertEqual(out['matched_pattern'], 'enhance transmissibility')
        self.assertEqual(out['offset'], 8)
        out = screen(doc('They increase virulence deliberately.'))
        self.assertEqual(out['verdict'], 'blocked:pathogen_enhancement')
        self.assertEqual(out['matched_pattern'], 'increase virulence')

    def test_harm_instruction_blocked(self):
        out = screen(doc('how to synthesize the toxin'))
        self.assertEqual(out['verdict'], 'blocked:harm_instruction')
        self.assertEqual(out['matched_pattern'], 'how to synthesize')
        self.assertEqual(out['offset'], 0)
        out = screen(doc('Notes on how to culture spores.'))
        self.assertEqual(out['verdict'], 'blocked:harm_instruction')
        self.assertEqual(out['matched_pattern'], 'how to culture')
        self.assertEqual(out['offset'], 9)
        out = screen(doc('They tried to weaponize it.'))
        self.assertEqual(out['verdict'], 'blocked:harm_instruction')
        self.assertEqual(out['matched_pattern'], 'weaponiz')
        self.assertEqual(out['offset'], 14)


class TestClearAndOrder(unittest.TestCase):
    def test_clean_in_silico_research_text_is_clear(self):
        out = screen(doc('We modeled the metabolic network in silico across 120 simulated '
                         'conditions and compared expression predictions with published datasets.',
                         kind='other'))
        self.assertEqual(out, {'id': 'd1', 'verdict': 'clear', 'category': None,
                               'matched_pattern': None, 'offset': None})

    def test_case_variants(self):
        for text in ('WE INCUBATE AT 37C.', 'Gain Of Function results.', 'HOW TO CULTURE cells.'):
            self.assertTrue(screen(doc(text))['verdict'].startswith('blocked:'))

    def test_first_match_follows_documented_pattern_order_not_offset(self):
        # harm phrase appears earlier in the string, but wet_lab_protocol is earlier
        # in the documented pattern order.
        out = screen(doc('how to synthesize peptides; we centrifuge samples.'))
        self.assertEqual(out['verdict'], 'blocked:wet_lab_protocol')
        self.assertEqual(out['matched_pattern'], 'centrifuge')
        self.assertEqual(out['offset'], 31)

    def test_determinism(self):
        d = doc('Add the culture medium now.')
        self.assertEqual(screen(d), screen(d))
        batch = [doc('clean text', 'b'), doc('pipette 5 ul', 'a')]
        self.assertEqual(screen_batch(batch), screen_batch(batch))

    def test_input_not_mutated(self):
        d = doc('Add the culture medium now.')
        snapshot = copy.deepcopy(d)
        screen(d)
        self.assertEqual(d, snapshot)
        batch = [doc('clean text', 'b'), d]
        screen_batch(batch)
        self.assertEqual(d, snapshot)


class TestRefusals(unittest.TestCase):
    def assert_code(self, code, document):
        with self.assertRaises(ValueError) as caught:
            screen(document)
        self.assertEqual(str(caught.exception), code)

    def test_unknown_fields(self):
        self.assert_code('P69:unknown_fields:document', doc('x', ) | {'extra': 1})
        self.assert_code('P69:unknown_fields:document', {'id': 'd1', 'kind': 'claim'})

    def test_empty_fields(self):
        self.assert_code('P69:empty_field:id', doc('clean text', doc_id=''))
        self.assert_code('P69:empty_field:id', doc('clean text', doc_id='   '))
        self.assert_code('P69:empty_field:text', doc(''))
        self.assert_code('P69:empty_field:text', doc('   '))

    def test_bad_kind(self):
        self.assert_code('P69:bad_kind:weird', doc('clean text', kind='weird'))
        self.assert_code('P69:bad_kind:', doc('clean text', kind=''))

    def test_bad_type(self):
        self.assert_code('P69:bad_type:document', 'not-a-dict')
        self.assert_code('P69:bad_type:id', {'id': 7, 'kind': 'claim', 'text': 'clean'})
        self.assert_code('P69:bad_type:kind', {'id': 'd', 'kind': 3, 'text': 'clean'})
        self.assert_code('P69:bad_type:text', {'id': 'd', 'kind': 'claim', 'text': 42})

    def test_length_bounds(self):
        screen(doc('x' * 4096))
        self.assert_code('P69:text_too_long:text', doc('x' * 4097))
        screen(doc('clean text', doc_id='i' * 64))
        self.assert_code('P69:id_too_long:id', doc('clean text', doc_id='i' * 65))

    def test_kind_values_accepted(self):
        for kind in ('protocol', 'instruction', 'claim', 'other'):
            self.assertEqual(screen(doc('clean text', kind=kind))['verdict'], 'clear')


class TestBatch(unittest.TestCase):
    def test_batch_sorted_order_and_blocked_is_verdict_not_refusal(self):
        out = screen_batch([doc('clean text', 'z'), doc('pipette 5 ul', 'a'),
                            doc('also clean', 'm', kind='claim')])
        self.assertEqual([v['id'] for v in out], ['a', 'm', 'z'])
        self.assertEqual(out[0]['verdict'], 'blocked:wet_lab_protocol')
        self.assertEqual(out[0]['matched_pattern'], 'pipette')
        self.assertEqual([v['verdict'] for v in out[1:]], ['clear', 'clear'])

    def test_batch_refuses_first_malformed_in_sorted_order(self):
        with self.assertRaises(ValueError) as caught:
            screen_batch([doc('clean text', 'z'), doc('', 'a'), doc('pipette 5 ul', 'm')])
        self.assertEqual(str(caught.exception), 'P69:empty_field:text')

    def test_batch_non_dict_member_refused_with_exact_code(self):
        # Pins the sort-guard AND: an AND->OR mutant would call int.get and
        # raise AttributeError instead of the promised ValueError code.
        with self.assertRaises(ValueError) as caught:
            screen_batch([1])
        self.assertEqual(str(caught.exception), 'P69:bad_type:document')

    def test_batch_type_refusal(self):
        with self.assertRaises(ValueError) as caught:
            screen_batch('not-a-list')
        self.assertEqual(str(caught.exception), 'P69:bad_type:documents')


class TestPatternListContract(unittest.TestCase):
    def test_module_pattern_list_equals_documented_list(self):
        self.assertEqual(PROHIBITED_PATTERNS, DOCUMENTED_PATTERNS)






class TestOffsetOriginalCoordinates(unittest.TestCase):
    def test_u0130_expansion_offset_is_in_original_text(self):
        # 'İ'.lower() expands to two codepoints (i + U+0307); the returned
        # offset must index the caller's original text, not the lowered copy.
        out = screen(doc('İ centrifuge'))
        self.assertEqual(out['verdict'], 'blocked:wet_lab_protocol')
        self.assertEqual(out['offset'], 2)
        self.assertEqual('İ centrifuge'[out['offset']:], 'centrifuge')

    def test_repeated_expanding_chars_accumulate_correctly(self):
        text = 'İİ centrifuge'
        out = screen(doc(text))
        self.assertEqual(out['offset'], 3)
        self.assertEqual(text[out['offset']:], 'centrifuge')
        text = 'İn İstanbul we incubate at 37C.'
        out = screen(doc(text))
        self.assertEqual(out['matched_pattern'], 'incubate at')
        self.assertEqual(text[out['offset']:], 'incubate at 37C.')

    def test_casefold_only_expansions_do_not_match(self):
        # Matching follows lower() semantics: 'ſ' (U+017F) casefolds to 's' but
        # lowercases to itself, so it is not an 's' for this screen.
        self.assertEqual(screen(doc('how to ſynthesize cells'))['verdict'], 'clear')

    def test_ascii_offsets_unchanged(self):
        out = screen(doc('We incubate at 37C overnight.'))
        self.assertEqual(out['offset'], 3)


if __name__ == '__main__':
    unittest.main()
