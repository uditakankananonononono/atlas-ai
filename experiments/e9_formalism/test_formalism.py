import unittest
from random import Random
from formalism import P, Operator, discover, berlekamp_massey, bounded_synthesis
from environment import make_environment, sequence, nth, switched_sequence


class FormalismTests(unittest.TestCase):
    def test_matrix_oracle_matches_direct(self):
        for family in ('dense','diagonal','jordan'):
            for dimension in range(1,9):
                m,s,o = make_environment(123+dimension,family,dimension)
                values = sequence(m,s,o,80)
                for n,v in enumerate(values):
                    self.assertEqual(nth(m,s,o,n),v)

    def test_out_of_seed_and_order_predictions(self):
        # Seeds disjoint from reported experiment; not report-only regression.
        for seed in (887,991,1109):
            for family in ('dense','diagonal','jordan'):
                for dimension in range(1,9):
                    m,s,o = make_environment(seed,family,dimension)
                    prefix = sequence(m,s,o,24)
                    model = discover(prefix)
                    self.assertIsNotNone(model)
                    for n in (0,1,23,24,47,1001,10**15+seed):
                        self.assertEqual(model.predict(n),nth(m,s,o,n))
                    coeff = berlekamp_massey(prefix[:16])
                    self.assertEqual(model.coeff,coeff)

    def test_composition_ring_laws(self):
        r = Random(192)
        for d in range(1,9):
            model = Operator(tuple(r.randrange(P) for _ in range(d)),(1,)*d)
            identity = (1,)+(0,)*(d-1)
            for _ in range(20):
                a,b,c = [tuple(r.randrange(P) for _ in range(d)) for _ in range(3)]
                self.assertEqual(model.compose(model.compose(a,b),c),model.compose(a,model.compose(b,c)))
                self.assertEqual(model.compose(a,identity),a)
                self.assertEqual(model.compose(a,b),model.compose(b,a))
                self.assertEqual(model.compose(model.power(87),model.power(56)),model.power(143))

    def test_reject_ambiguous_and_corrupt(self):
        self.assertIsNone(discover([0]*24))
        m,s,o = make_environment(91,'dense',4)
        prefix = sequence(m,s,o,24)
        prefix[-1] = (prefix[-1]+1)%P
        self.assertIsNone(discover(prefix))

    def test_input_and_budget_contracts(self):
        for n in (-1,True,2.0):
            with self.assertRaises(ValueError):
                Operator((2,),(3,)).predict(n)
        for seq in ([1]*16,[-1]*24,[True]*24):
            with self.assertRaises(ValueError):
                discover(seq)
        op,count,reason = bounded_synthesis(list(range(24)),budget=1)
        self.assertIsNone(op)
        self.assertEqual((count,reason),(1,'budget_exhausted'))

    def test_delayed_change_is_an_explicit_failure(self):
        # Scalar state evolves by *2 before t=24, then by *3. Outputs are
        # generated from continuous state, not oracle answers altered by +1.
        changed = switched_sequence([[2]],[[3]],[1],[1],101,24)
        self.assertEqual(changed[:24],[pow(2,i,P) for i in range(24)])
        self.assertEqual(changed[100],pow(2,24,P)*pow(3,76,P)%P)
        op = discover(changed[:24])
        self.assertIsNotNone(op)
        self.assertEqual(op.predict(100),pow(2,100,P))
        self.assertNotEqual(op.predict(100),changed[100])


if __name__ == '__main__':
    unittest.main()
