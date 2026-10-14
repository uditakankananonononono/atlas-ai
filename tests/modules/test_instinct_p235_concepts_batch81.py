"""Tests for P235 concepts batch 81 (doc 801-810)."""
import itertools
import random
import unittest
from collections import Counter

from app.modules.instinct_doc import p235_concepts_batch81 as m
from app.modules.instinct_doc import p235_concepts_registry as reg


class TestNQueens(unittest.TestCase):
    def test_canonical(self):
        self.assertEqual(m.n_queens_count(1), 1)
        self.assertEqual(m.n_queens_count(2), 0)
        self.assertEqual(m.n_queens_count(4), 2)
        self.assertEqual(m.n_queens_count(8), 92)

    def test_refusals(self):
        with self.assertRaises(ValueError):
            m.n_queens_count(0)
        with self.assertRaises(ValueError):
            m.n_queens_count(13)
        with self.assertRaises(ValueError):
            m.n_queens_count(True)
        with self.assertRaises(ValueError):
            m.n_queens_count("8")

    def test_oracle_brute_force_permutations(self):
        def oracle(n):
            count = 0
            for perm in itertools.permutations(range(n)):
                ok = True
                for i in range(n):
                    for j in range(i + 1, n):
                        if abs(perm[i] - perm[j]) == j - i:
                            ok = False
                            break
                    if not ok:
                        break
                count += ok
            return count
        for n in range(1, 8):
            self.assertEqual(m.n_queens_count(n), oracle(n))


class TestRailFence(unittest.TestCase):
    def test_canonical(self):
        self.assertEqual(m.rail_fence_encode("WEAREDISCOVEREDFLEEATONCE", 3),
                         "WECRLTEERDSOEEFEAOCAIVDEN")
        self.assertEqual(m.rail_fence_decode("WECRLTEERDSOEEFEAOCAIVDEN", 3),
                         "WEAREDISCOVEREDFLEEATONCE")
        self.assertEqual(m.rail_fence_encode("abc", 5), "abc")
        self.assertEqual(m.rail_fence_decode("abc", 5), "abc")

    def test_refusals(self):
        for fn in (m.rail_fence_encode, m.rail_fence_decode):
            with self.assertRaises(ValueError):
                fn("", 3)
            with self.assertRaises(ValueError):
                fn("abc", 1)
            with self.assertRaises(ValueError):
                fn("abc", 101)
            with self.assertRaises(ValueError):
                fn("abéc", 2)
            with self.assertRaises(ValueError):
                fn(["abc"], 2)
            with self.assertRaises(ValueError):
                fn("abc", "2")

    def test_oracle_reference_and_roundtrip(self):
        def oracle_encode(text, rails):
            if rails >= len(text):
                return text
            period = 2 * rails - 2
            out = []
            for r in range(rails):
                i = r
                while i < len(text):
                    out.append(text[i])
                    j = i + (period - 2 * r)
                    if r not in (0, rails - 1) and j < len(text):
                        out.append(text[j])
                    i += period
            return "".join(out)
        rng = random.Random(8101)
        for _ in range(200):
            text = "".join(rng.choice("abcXYZ 09!")
                           for _ in range(rng.randint(1, 40)))
            rails = rng.randint(2, 12)
            self.assertEqual(m.rail_fence_encode(text, rails),
                             oracle_encode(text, rails))
            self.assertEqual(
                m.rail_fence_decode(m.rail_fence_encode(text, rails), rails),
                text)


class TestBordaAndCondorcet(unittest.TestCase):
    def test_canonical(self):
        ballots = [["a", "b", "c"], ["a", "c", "b"], ["b", "a", "c"]]
        self.assertEqual(m.borda_count_winner(ballots), "a")
        self.assertEqual(m.condorcet_winner(
            [["a", "b", "c"], ["b", "a", "c"], ["c", "a", "b"]]), "a")
        self.assertIsNone(m.condorcet_winner(
            [["a", "b", "c"], ["b", "c", "a"], ["c", "a", "b"]]))
        self.assertIsNone(m.borda_count_winner(
            [["a", "b"], ["b", "a"]]))

    def test_refusals(self):
        for fn in (m.borda_count_winner, m.condorcet_winner):
            with self.assertRaises(ValueError):
                fn([])
            with self.assertRaises(ValueError):
                fn([["a", "b"], ["a"]])
            with self.assertRaises(ValueError):
                fn([["a", "a"]])
            with self.assertRaises(ValueError):
                fn([["A", "b"]])
            with self.assertRaises(ValueError):
                fn([["a", "b"], ("a", "b")])
            with self.assertRaises(ValueError):
                fn([[""]])

    def test_oracle_brute_scores(self):
        def borda_oracle(ballots):
            scores = Counter()
            k = len(ballots[0])
            for ballot in ballots:
                for rank, name in enumerate(ballot):
                    scores[name] += k - 1 - rank
            top = max(scores.values())
            winners = [n for n, v in scores.items() if v == top]
            return winners[0] if len(winners) == 1 else None

        def condorcet_oracle(ballots):
            names = set(ballots[0])
            for x in names:
                if all(x == y or
                       sum(ballot.index(x) < ballot.index(y)
                           for ballot in ballots) * 2 > len(ballots)
                       for y in names):
                    return x
            return None
        rng = random.Random(8102)
        for _ in range(300):
            names = ["a", "b", "c", "d"][:rng.randint(2, 4)]
            ballots = []
            for _ in range(rng.randint(1, 9)):
                perm = names[:]
                rng.shuffle(perm)
                ballots.append(perm)
            self.assertEqual(m.borda_count_winner(ballots),
                             borda_oracle(ballots))
            self.assertEqual(m.condorcet_winner(ballots),
                             condorcet_oracle(ballots))

    def test_borda_condorcet_can_disagree(self):
        ballots = ([["a", "b", "c"]] * 3 + [["b", "c", "a"]] * 2 +
                   [["b", "a", "c"]] + [["c", "a", "b"]])
        self.assertEqual(m.borda_count_winner(ballots), "b")
        self.assertEqual(m.condorcet_winner(ballots), "a")


class TestPokerHand(unittest.TestCase):
    def test_canonical(self):
        self.assertEqual(m.poker_hand_category(
            ["AH", "KH", "QH", "JH", "TH"]), "straight_flush")
        self.assertEqual(m.poker_hand_category(
            ["AS", "2D", "3C", "4H", "5S"]), "straight")
        self.assertEqual(m.poker_hand_category(
            ["AS", "AD", "AC", "AH", "5S"]), "four_of_a_kind")
        self.assertEqual(m.poker_hand_category(
            ["AS", "AD", "AC", "KH", "KS"]), "full_house")
        self.assertEqual(m.poker_hand_category(
            ["2H", "5H", "9H", "JH", "KH"]), "flush")
        self.assertEqual(m.poker_hand_category(
            ["AS", "AD", "AC", "KH", "5S"]), "three_of_a_kind")
        self.assertEqual(m.poker_hand_category(
            ["AS", "AD", "KC", "KH", "5S"]), "two_pair")
        self.assertEqual(m.poker_hand_category(
            ["AS", "AD", "KC", "QH", "5S"]), "one_pair")
        self.assertEqual(m.poker_hand_category(
            ["AS", "2D", "4C", "7H", "9S"]), "high_card")

    def test_refusals(self):
        with self.assertRaises(ValueError):
            m.poker_hand_category(["AS", "AS", "KC", "QH", "5S"])
        with self.assertRaises(ValueError):
            m.poker_hand_category(["AS", "AD", "KC", "QH"])
        with self.assertRaises(ValueError):
            m.poker_hand_category(["1S", "AD", "KC", "QH", "5S"])
        with self.assertRaises(ValueError):
            m.poker_hand_category(["AX", "AD", "KC", "QH", "5S"])
        with self.assertRaises(ValueError):
            m.poker_hand_category(["ASH", "AD", "KC", "QH", "5S"])
        with self.assertRaises(ValueError):
            m.poker_hand_category(("AS", "AD", "KC", "QH", "5S"))

    def test_oracle_alternate_classifier(self):
        def oracle(cards):
            ranks = sorted("23456789TJQKA".index(c[0]) for c in cards)
            flush = len({c[1] for c in cards}) == 1
            run = list(Counter(ranks).values())
            run.sort(reverse=True)
            uniq = sorted(set(ranks))
            straight = len(uniq) == 5 and (
                uniq[-1] - uniq[0] == 4 or uniq == [0, 1, 2, 3, 12])
            if straight and flush:
                return "straight_flush"
            table = {(4, 1): "four_of_a_kind", (3, 2): "full_house",
                     (3, 1, 1): "three_of_a_kind", (2, 2, 1): "two_pair",
                     (2, 1, 1, 1): "one_pair"}
            if flush:
                return "flush"
            if straight:
                return "straight"
            return table.get(tuple(run), "high_card")
        rng = random.Random(8103)
        deck = [r + s for r in "23456789TJQKA" for s in "CDHS"]
        for _ in range(4000):
            hand = rng.sample(deck, 5)
            self.assertEqual(m.poker_hand_category(hand), oracle(hand))


class TestConnectFour(unittest.TestCase):
    def test_canonical(self):
        col_win = [".......", ".......", "X......", "X......",
                   "X......", "XO....."]
        self.assertEqual(m.connect_four_winner(col_win), "X")
        diag_win = [".......", ".......", "...X...", "..XO...",
                    ".XOO...", "XOOO..."]
        self.assertEqual(m.connect_four_winner(diag_win), "X")
        self.assertIsNone(m.connect_four_winner(
            [".......", ".......", ".......", ".......",
             "X......", "XO....."]))
        self.assertIsNone(m.connect_four_winner(["......."] * 6))

    def test_refusals(self):
        with self.assertRaises(ValueError):
            m.connect_four_winner(["......."] * 5)
        with self.assertRaises(ValueError):
            m.connect_four_winner(["......"] * 6)
        with self.assertRaises(ValueError):
            m.connect_four_winner([".......", ".......", "X......",
                                   ".......", "X......", "X......"])
        with self.assertRaises(ValueError):
            m.connect_four_winner([".......", ".......", "X......",
                                   "X......", "X......", "XO....."][:-1]
                                  + ["XOOOOOX"])
        with self.assertRaises(ValueError):
            m.connect_four_winner([".......", ".......", "X......",
                                   "X......", "X......", "XO....."][:4]
                                  + ["A......", "X......"])

    def test_oracle_alternate_scan(self):
        def oracle(grid):
            wins = set()
            cells = [list(row) for row in grid]
            for line_r in range(6):
                for line_c in range(7):
                    for dr, dc in ((0, 1), (1, 0), (1, 1), (1, -1)):
                        seq = []
                        for i in range(4):
                            r, c = line_r + dr * i, line_c + dc * i
                            if not (0 <= r < 6 and 0 <= c < 7):
                                break
                            seq.append(cells[r][c])
                        if len(seq) == 4 and seq[0] != "." \
                                and len(set(seq)) == 1:
                            wins.add(seq[0])
            if len(wins) > 1:
                return "INVALID"
            return wins.pop() if wins else None
        rng = random.Random(8104)
        for _ in range(500):
            cols = []
            for _ in range(7):
                height = rng.randint(0, 6)
                col = (["X", "O"][rng.randint(0, 1)] for _ in range(height))
                cols.append(list(col))
            grid = []
            for r in range(6):
                row = ""
                for c in range(7):
                    stack = cols[c]
                    idx = 5 - r
                    row += stack[idx] if idx < len(stack) else "."
                grid.append(row)
            want = oracle(grid)
            try:
                got = m.connect_four_winner(grid)
            except ValueError:
                got = "INVALID"
            self.assertEqual(got, want)


class TestMinesweeper(unittest.TestCase):
    def test_canonical(self):
        self.assertEqual(m.minesweeper_reveal(
            ["..M", "...", "M.."], [0, 0]), ["01M", "12.", "M.."])
        self.assertEqual(m.minesweeper_reveal(
            ["..M", "...", "M.."], [0, 2]), ["..X", "...", "M.."])
        self.assertEqual(m.minesweeper_reveal(
            ["..M", "...", "M.."], [0, 1]), [".1M", "...", "M.."])

    def test_refusals(self):
        with self.assertRaises(ValueError):
            m.minesweeper_reveal([], [0, 0])
        with self.assertRaises(ValueError):
            m.minesweeper_reveal(["..M", ".."], [0, 0])
        with self.assertRaises(ValueError):
            m.minesweeper_reveal(["..X"], [0, 0])
        with self.assertRaises(ValueError):
            m.minesweeper_reveal(["..M"], [0, 3])
        with self.assertRaises(ValueError):
            m.minesweeper_reveal(["..M"], [0])
        with self.assertRaises(ValueError):
            m.minesweeper_reveal(["..M"], [0.0, 0])

    def test_oracle_alternate_flood(self):
        def oracle(board, click):
            h, w = len(board), len(board[0])
            out = [list(row) for row in board]
            r0, c0 = click

            def mines(r, c):
                return sum(1 for dr in (-1, 0, 1) for dc in (-1, 0, 1)
                           if (dr or dc) and 0 <= r + dr < h
                           and 0 <= c + dc < w
                           and board[r + dr][c + dc] == "M")
            if board[r0][c0] == "M":
                out[r0][c0] = "X"
                return ["".join(row) for row in out]
            stack = [(r0, c0)]
            done = set()
            while stack:
                r, c = stack.pop()
                if (r, c) in done:
                    continue
                done.add((r, c))
                total = mines(r, c)
                out[r][c] = str(total)
                if total == 0:
                    for dr in (-1, 0, 1):
                        for dc in (-1, 0, 1):
                            nr, nc = r + dr, c + dc
                            if (dr or dc) and 0 <= nr < h and 0 <= nc < w \
                                    and board[nr][nc] == "." \
                                    and (nr, nc) not in done:
                                stack.append((nr, nc))
            return ["".join(row) for row in out]
        rng = random.Random(8105)
        for _ in range(300):
            h, w = rng.randint(1, 6), rng.randint(1, 6)
            board = ["".join("M" if rng.random() < 0.2 else "."
                             for _ in range(w)) for _ in range(h)]
            click = [rng.randint(0, h - 1), rng.randint(0, w - 1)]
            self.assertEqual(m.minesweeper_reveal(board, click),
                             oracle(board, click))


class TestKClosest(unittest.TestCase):
    def test_canonical(self):
        self.assertEqual(m.k_closest_points_origin([[1, 3], [-2, 2]], 1),
                         [[-2, 2]])
        self.assertEqual(m.k_closest_points_origin(
            [[3, 3], [5, -1], [-2, 4]], 2), [[3, 3], [-2, 4]])
        self.assertEqual(m.k_closest_points_origin([[1, 0]], 0), [])
        self.assertEqual(m.k_closest_points_origin(
            [[0, 1], [1, 0]], 2), [[0, 1], [1, 0]])

    def test_refusals(self):
        with self.assertRaises(ValueError):
            m.k_closest_points_origin([[1, 2]], 2)
        with self.assertRaises(ValueError):
            m.k_closest_points_origin([[1, 2]], -1)
        with self.assertRaises(ValueError):
            m.k_closest_points_origin([[1]], 1)
        with self.assertRaises(ValueError):
            m.k_closest_points_origin([(1, 2)], 1)
        with self.assertRaises(ValueError):
            m.k_closest_points_origin([[10 ** 10, 0]], 1)
        with self.assertRaises(ValueError):
            m.k_closest_points_origin([[1.5, 0]], 1)

    def test_oracle_full_sort(self):
        rng = random.Random(8106)
        for _ in range(300):
            points = [[rng.randint(-50, 50), rng.randint(-50, 50)]
                      for _ in range(rng.randint(0, 30))]
            k = rng.randint(0, len(points))
            want = [p for _, _, p in sorted(
                (x * x + y * y, i, [x, y])
                for i, (x, y) in enumerate(points))[:k]]
            self.assertEqual(m.k_closest_points_origin(points, k), want)


class TestElementaryCellular(unittest.TestCase):
    def test_canonical(self):
        self.assertEqual(m.elementary_cellular_step(
            90, [0, 0, 0, 1, 0, 0, 0]), [0, 0, 1, 0, 1, 0, 0])
        self.assertEqual(m.elementary_cellular_step(
            30, [1, 1, 0, 1, 0]), [1, 0, 0, 1, 0])
        self.assertEqual(m.elementary_cellular_step(0, [1, 1, 1]),
                         [0, 0, 0])
        self.assertEqual(m.elementary_cellular_step(255, [0, 0, 0]),
                         [1, 1, 1])

    def test_refusals(self):
        with self.assertRaises(ValueError):
            m.elementary_cellular_step(256, [1])
        with self.assertRaises(ValueError):
            m.elementary_cellular_step(-1, [1])
        with self.assertRaises(ValueError):
            m.elementary_cellular_step(90, [])
        with self.assertRaises(ValueError):
            m.elementary_cellular_step(90, [2])
        with self.assertRaises(ValueError):
            m.elementary_cellular_step(90, [True])
        with self.assertRaises(ValueError):
            m.elementary_cellular_step("90", [1])

    def test_oracle_rule_table(self):
        def oracle(rule, state):
            table = {}
            for hood in range(8):
                table[hood] = (rule >> hood) & 1
            n = len(state)
            nxt = []
            for i in range(n):
                left = state[i - 1] if i > 0 else state[n - 1]
                right = state[i + 1] if i < n - 1 else state[0]
                nxt.append(table[left * 4 + state[i] * 2 + right])
            return nxt
        rng = random.Random(8107)
        for _ in range(300):
            rule = rng.randint(0, 255)
            state = [rng.randint(0, 1)
                     for _ in range(rng.randint(1, 20))]
            self.assertEqual(m.elementary_cellular_step(rule, state),
                             oracle(rule, state))


class TestRegistryKnowsBatch81(unittest.TestCase):
    def test_registry_knows_batch81(self):
        names = {e["name"] for e in reg.ENTRIES}
        for name in ("n_queens_count", "rail_fence_encode",
                     "rail_fence_decode", "borda_count_winner",
                     "condorcet_winner", "poker_hand_category",
                     "connect_four_winner", "minesweeper_reveal",
                     "k_closest_points_origin",
                     "elementary_cellular_step"):
            self.assertIn(name, names)


if __name__ == "__main__":
    unittest.main()
