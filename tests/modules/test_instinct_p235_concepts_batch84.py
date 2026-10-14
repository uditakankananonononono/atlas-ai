"""Tests for P235 concepts batch 84 (binary tree algorithms)."""

import random
import unittest

from app.modules.instinct_doc import p235_concepts_batch84 as m
from app.modules.instinct_doc import p235_concepts_registry as reg

MAX_ITEMS = reg.MAX_ITEMS

TREE = [1, [2, [4, None, None], [5, None, None]], [3, None, None]]
LC_TREE = [-10, [9, None, None],
           [20, [15, None, None], [7, None, None]]]

def refusal(code):
    return "P235:" + code

def make_tree(rng, size, lo=-9, hi=9, unique=False):
    """Build a random nested tree with exactly size nodes."""
    values = (rng.sample(range(lo, hi + 1), size) if unique
              else [rng.randint(lo, hi) for _ in range(size)])
    root = [values[0], None, None]
    slots = [(root, 1), (root, 2)]
    for v in values[1:]:
        node, pos = slots.pop(rng.randrange(len(slots)))
        child = [v, None, None]
        node[pos] = child
        slots.append((child, 1))
        slots.append((child, 2))
    return root

def parent_map(root):
    parent = {id(root): None}
    stack = [root]
    while stack:
        node = stack.pop()
        for child in (node[1], node[2]):
            if child is not None:
                parent[id(child)] = node
                stack.append(child)
    return parent

def path_between(parent, u, v):
    up = {}
    node, dist = u, 0
    while node is not None:
        up[id(node)] = dist
        node, dist = parent[id(node)], dist + 1
    node, dist = v, 0
    while id(node) not in up:
        node, dist = parent[id(node)], dist + 1
    return up[id(node)] + dist

def all_nodes(root):
    out, stack = [], [root]
    while stack:
        node = stack.pop()
        out.append(node)
        stack.extend(c for c in (node[1], node[2]) if c is not None)
    return out

class TestTreeIsBalancedCheck(unittest.TestCase):
    def test_canonical(self):
        self.assertTrue(m.tree_is_balanced_check(TREE))
        self.assertTrue(m.tree_is_balanced_check([5, None, None]))
        self.assertFalse(m.tree_is_balanced_check(
            [1, [2, [3, None, None], None], None]))
        self.assertTrue(m.tree_is_balanced_check(
            [1, [2, None, None], [3, None, [4, None, None]]]))

    def test_oracle(self):
        def height(node):
            if node is None:
                return 0
            return 1 + max(height(node[1]), height(node[2]))

        def oracle(node):
            if node is None:
                return True
            return (abs(height(node[1]) - height(node[2])) <= 1
                    and oracle(node[1]) and oracle(node[2]))
        rng = random.Random(8403)
        for _ in range(60):
            tree = make_tree(rng, rng.randint(1, 12))
            self.assertEqual(m.tree_is_balanced_check(tree), oracle(tree))

class TestTreePathSumExists(unittest.TestCase):
    def test_canonical(self):
        self.assertTrue(m.tree_path_sum_exists(TREE, 8))
        self.assertTrue(m.tree_path_sum_exists(TREE, 7))
        self.assertFalse(m.tree_path_sum_exists(TREE, 100))
        self.assertFalse(m.tree_path_sum_exists(TREE, 3))
        self.assertTrue(m.tree_path_sum_exists(
            [-1, [-2, None, None], None], -3))

    def test_refusals(self):
        with self.assertRaises(ValueError) as ctx:
            m.tree_path_sum_exists(TREE, "8")
        self.assertEqual(str(ctx.exception),
                         refusal("tree_path_sum_exists:bad_type:target"))

    def test_oracle(self):
        def oracle(node, target):
            if node[1] is None and node[2] is None:
                return node[0] == target
            return ((node[1] is not None
                     and oracle(node[1], target - node[0]))
                    or (node[2] is not None
                        and oracle(node[2], target - node[0])))
        rng = random.Random(8404)
        for _ in range(60):
            tree = make_tree(rng, rng.randint(1, 10))
            target = rng.randint(-20, 30)
            self.assertEqual(m.tree_path_sum_exists(tree, target),
                             oracle(tree, target))

class TestTreeMaxPathSum(unittest.TestCase):
    def test_canonical(self):
        self.assertEqual(m.tree_max_path_sum(TREE), 11)
        self.assertEqual(m.tree_max_path_sum(LC_TREE), 42)
        self.assertEqual(m.tree_max_path_sum(
            [-3, [-1, None, None], [-2, None, None]]), -1)
        self.assertEqual(m.tree_max_path_sum([7, None, None]), 7)

    def test_oracle(self):
        def oracle(root):
            parent = parent_map(root)
            nodes = all_nodes(root)
            best = None
            for i, u in enumerate(nodes):
                for v in nodes[i:]:
                    # path u..v via the join: sum both root walks minus
                    # the shared ancestors below the join
                    up = {}
                    node = u
                    while node is not None:
                        up[id(node)] = node
                        node = parent[id(node)]
                    node = v
                    while id(node) not in up:
                        node = parent[id(node)]
                    join = node
                    total = 0
                    node = u
                    while node is not join:
                        total += node[0]
                        node = parent[id(node)]
                    node = v
                    while node is not join:
                        total += node[0]
                        node = parent[id(node)]
                    total += join[0]
                    if best is None or total > best:
                        best = total
            return best
        rng = random.Random(8405)
        for _ in range(60):
            tree = make_tree(rng, rng.randint(1, 9))
            self.assertEqual(m.tree_max_path_sum(tree), oracle(tree))

class TestTreeMirrorInvert(unittest.TestCase):
    def test_canonical(self):
        original = [1, [2, [4, None, None], [5, None, None]],
                    [3, None, None]]
        snapshot = [1, [2, [4, None, None], [5, None, None]],
                    [3, None, None]]
        flipped = m.tree_mirror_invert(original)
        self.assertEqual(flipped, [1, [3, None, None],
                                   [2, [5, None, None],
                                    [4, None, None]]])
        self.assertEqual(original, snapshot)
        self.assertEqual(m.tree_mirror_invert([5, None, None]),
                         [5, None, None])

    def test_oracle(self):
        def oracle(node):
            if node is None:
                return None
            return [node[0], oracle(node[2]), oracle(node[1])]
        rng = random.Random(8406)
        for _ in range(60):
            tree = make_tree(rng, rng.randint(1, 12))
            self.assertEqual(m.tree_mirror_invert(tree), oracle(tree))

class TestTreeCompleteCheck(unittest.TestCase):
    def test_canonical(self):
        self.assertTrue(m.tree_complete_check(
            [1, [2, [4, None, None], [5, None, None]],
             [3, [6, None, None], None]]))
        self.assertFalse(m.tree_complete_check(
            [1, [2, [4, None, None], [5, None, None]],
             [3, None, [7, None, None]]]))
        self.assertFalse(m.tree_complete_check(
            [1, [2, None, [5, None, None]], [3, None, None]]))
        self.assertTrue(m.tree_complete_check([5, None, None]))
        self.assertTrue(m.tree_complete_check(
            [1, [2, None, None], None]))
        self.assertFalse(m.tree_complete_check(
            [1, None, [3, None, None]]))

    def test_oracle(self):
        def oracle(root):
            # heap indexing: complete iff the largest assigned
            # index equals the node count minus one
            seen = [(root, 0)]
            count = 0
            top = 0
            while seen:
                node, idx = seen.pop()
                count += 1
                top = max(top, idx)
                for off, child in ((1, node[1]), (2, node[2])):
                    if child is not None:
                        seen.append((child, 2 * idx + off))
            return top == count - 1
        rng = random.Random(8407)
        for _ in range(60):
            tree = make_tree(rng, rng.randint(1, 12))
            self.assertEqual(m.tree_complete_check(tree), oracle(tree))

class TestTreeLowestCommonAncestor(unittest.TestCase):
    def test_canonical(self):
        self.assertEqual(m.tree_lowest_common_ancestor(TREE, 4, 5), 2)
        self.assertEqual(m.tree_lowest_common_ancestor(TREE, 4, 2), 2)
        self.assertEqual(m.tree_lowest_common_ancestor(TREE, 4, 3), 1)
        self.assertEqual(m.tree_lowest_common_ancestor(TREE, 1, 5), 1)

    def test_refusals(self):
        with self.assertRaises(ValueError) as ctx:
            m.tree_lowest_common_ancestor(TREE, 4, 99)
        self.assertEqual(str(ctx.exception), refusal(
            "tree_lowest_common_ancestor:missing:value_b"))
        with self.assertRaises(ValueError) as ctx:
            m.tree_lowest_common_ancestor(TREE, 99, 4)
        self.assertEqual(str(ctx.exception), refusal(
            "tree_lowest_common_ancestor:missing:value_a"))
        dup = [1, [2, None, None], [2, None, None]]
        with self.assertRaises(ValueError) as ctx:
            m.tree_lowest_common_ancestor(dup, 1, 2)
        self.assertEqual(str(ctx.exception), refusal(
            "tree_lowest_common_ancestor:duplicate:value"))

    def test_oracle(self):
        def find(node, value):
            if node is None:
                return None
            if node[0] == value:
                return node
            return find(node[1], value) or find(node[2], value)

        def oracle(node, a, b):
            na = find(node, a)
            if na is not None and (find(na, b) is not None):
                pass
            contains_b = find(node, b) is not None
            if node[0] in (a, b):
                return node[0]
            left = (find(node[1], a) is not None
                    and find(node[1], b) is not None)
            right = (find(node[2], a) is not None
                     and find(node[2], b) is not None)
            if left:
                return oracle(node[1], a, b)
            if right:
                return oracle(node[2], a, b)
            return node[0]
        rng = random.Random(8408)
        for _ in range(60):
            size = rng.randint(1, 12)
            tree = make_tree(rng, size, unique=True)
            vals = [n[0] for n in all_nodes(tree)]
            a = rng.choice(vals)
            b = rng.choice(vals)
            self.assertEqual(m.tree_lowest_common_ancestor(tree, a, b),
                             oracle(tree, a, b))

class TestTreeLevelSumsMax(unittest.TestCase):
    def test_canonical(self):
        self.assertEqual(m.tree_level_sums_max(TREE), 9)
        self.assertEqual(m.tree_level_sums_max(
            [1, [2, None, None], [-5, None, None]]), 1)
        self.assertEqual(m.tree_level_sums_max([7, None, None]), 7)

    def test_oracle(self):
        def oracle(root):
            sums = {}

            def walk(node, depth):
                sums[depth] = sums.get(depth, 0) + node[0]
                for child in (node[1], node[2]):
                    if child is not None:
                        walk(child, depth + 1)
            walk(root, 0)
            return max(sums.values())
        rng = random.Random(8409)
        for _ in range(60):
            tree = make_tree(rng, rng.randint(1, 12))
            self.assertEqual(m.tree_level_sums_max(tree), oracle(tree))

class TestTreeRightSideView(unittest.TestCase):
    def test_canonical(self):
        self.assertEqual(m.tree_right_side_view(TREE), [1, 3, 5])
        self.assertEqual(m.tree_right_side_view(
            [1, None, [2, None, [3, None, None]]]), [1, 2, 3])
        self.assertEqual(m.tree_right_side_view(
            [1, [2, None, [5, None, None]],
             [3, None, [4, None, None]]]), [1, 3, 4])
        self.assertEqual(m.tree_right_side_view([7, None, None]), [7])

    def test_oracle(self):
        def oracle(root):
            seen = {}

            def walk(node, depth):
                if node is None:
                    return
                if depth not in seen:
                    seen[depth] = node[0]
                walk(node[2], depth + 1)
                walk(node[1], depth + 1)
            walk(root, 0)
            return [seen[d] for d in sorted(seen)]
        rng = random.Random(8410)
        for _ in range(60):
            tree = make_tree(rng, rng.randint(1, 12))
            self.assertEqual(m.tree_right_side_view(tree), oracle(tree))

class TestRegistryKnowsBatch84(unittest.TestCase):
    def test_registry_knows_batch84(self):
        names = {e["name"] for e in reg.ENTRIES}
        for name in ("tree_is_balanced_check", "tree_path_sum_exists",
                     "tree_max_path_sum", "tree_mirror_invert",
                     "tree_complete_check", "tree_lowest_common_ancestor",
                     "tree_level_sums_max", "tree_right_side_view"):
            self.assertIn(name, names)

if __name__ == "__main__":
    unittest.main()
