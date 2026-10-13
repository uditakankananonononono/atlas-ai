import math
import unittest
from critique import Policy, make_graph, transform, reference, metric, auc, admit


class CritiqueTests(unittest.TestCase):
    def test_strong_solver_matches_independent_oracle(self):
        for seed in range(200,400):
            g,s,t = make_graph(seed,'challenge')
            self.assertEqual(Policy('test','dijkstra').solve(g,s,t),reference(g,s,t))

    def test_transformation_specifications(self):
        for seed in range(700,750):
            g,s,t = make_graph(seed,'challenge')
            for kind in ('relabel','subdivide','irrelevant_component'):
                ng,ns,nt = transform(g,s,t,kind,seed)
                self.assertEqual(reference(g,s,t),reference(ng,ns,nt))
                self.assertEqual(Policy('exact','dijkstra').solve(ng,ns,nt),reference(ng,ns,nt))

    def test_old_metric_misses_weighted_failure(self):
        g = {0:[(1,1),(2,10)],1:[(2,1)],2:[]}
        self.assertEqual(Policy('bfs','bfs').solve(g,0,2),10)
        self.assertEqual(reference(g,0,2),2)

    def test_auc_and_fail_closed_admission(self):
        self.assertEqual(auc([0,0,1,1],[False,False,True,True]),1)
        self.assertEqual(auc([0,0],[False,True]),.5)
        self.assertFalse(admit({'constant':[0]*8},[False]*4+[True]*4,permutations=99)['admitted'])
        self.assertFalse(admit({'any':[0,1]},[True,True],permutations=99)['admitted'])

    def test_wrong_but_invariant_is_not_success(self):
        class AlwaysZero:
            def solve(self,graph,source,target):
                return 0
        from critique import external_error
        cases = [make_graph(i,'challenge') for i in range(600,620)]
        self.assertEqual(metric(AlwaysZero(),cases,'relabel'),0)
        self.assertEqual(external_error(AlwaysZero(),cases),1)

    def test_unreachable_oracle_and_policy(self):
        g = {0:[],1:[]}
        self.assertEqual(reference(g,0,1),math.inf)
        self.assertEqual(Policy('exact','dijkstra').solve(g,0,1),math.inf)


if __name__ == '__main__':
    unittest.main()
