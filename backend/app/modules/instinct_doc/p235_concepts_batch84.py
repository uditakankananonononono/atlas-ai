"""P235 concepts batch 84: binary tree algorithms.

Trees are nested lists [value, left, right]; left and right are
None or subtrees, values are ints in -10000..10000, and a tree
holds at most MAX_ITEMS (10000) nodes. Every function validates
the whole tree before answering and traverses iteratively, so a
10000-node chain never touches the interpreter recursion limit.
Coded refusals, no external deps, no mutation of the input tree.
"""

from app.modules.instinct_doc.p235_concepts_registry import (
    MAX_ITEMS, check_int, make_fail)

MAX_VAL = 10_000

def _tree(fail, root, unique=False):
    """Validate a nested [value, left, right] tree; return node count.

    The unique=True branch (with its duplicate check) is exercised
    only by tree_lowest_common_ancestor; callers that pass the
    default do not cover it."""
    if root is None:
        fail("empty:tree")
    if type(root) is not list:
        fail("bad_type:tree")
    count = 0
    seen = set()
    stack = [root]
    while stack:
        node = stack.pop()
        if type(node) is not list or len(node) != 3:
            fail("bad_shape:tree")
        value, left, right = node
        check_int(fail, value, "value")
        if value < -MAX_VAL or value > MAX_VAL:
            fail("out_of_range:value")
        if unique:
            if value in seen:
                fail("duplicate:value")
            seen.add(value)
        count += 1
        if count > MAX_ITEMS:
            fail("too_many:tree")
        for child in (left, right):
            if child is not None:
                if type(child) is not list:
                    fail("bad_shape:tree")
                stack.append(child)
    return count

def tree_is_balanced_check(root):
    """True when every node's subtree heights differ by at most one."""
    fail = make_fail("tree_is_balanced_check")
    _tree(fail, root)
    heights = {}
    order = []
    stack = [(root, False)]
    while stack:
        node, done = stack.pop()
        if node is None:
            continue
        if done:
            order.append(node)
        else:
            stack.append((node, True))
            stack.append((node[2], False))
            stack.append((node[1], False))
    for node in order:
        left = heights.get(id(node[1]), 0)
        right = heights.get(id(node[2]), 0)
        if abs(left - right) > 1:
            return False
        heights[id(node)] = 1 + max(left, right)
    return True

def tree_path_sum_exists(root, target):
    """True when some root-to-leaf path sums exactly to target.

    Only full root-to-leaf paths count, and every node value on
    the path is included."""
    fail = make_fail("tree_path_sum_exists")
    _tree(fail, root)
    check_int(fail, target, "target")
    stack = [(root, root[0])]
    while stack:
        node, total = stack.pop()
        left, right = node[1], node[2]
        if left is None and right is None:
            if total == target:
                return True
            continue
        for child in (left, right):
            if child is not None:
                stack.append((child, total + child[0]))
    return False

def tree_max_path_sum(root):
    """Largest sum over any path between any two nodes.

    The path follows parent-child edges in either direction and
    must hold at least one node, so an all-negative tree answers
    its largest single value."""
    fail = make_fail("tree_max_path_sum")
    _tree(fail, root)
    gains = {}
    best = [None]
    order = []
    stack = [(root, False)]
    while stack:
        node, done = stack.pop()
        if node is None:
            continue
        if done:
            order.append(node)
        else:
            stack.append((node, True))
            stack.append((node[2], False))
            stack.append((node[1], False))
    for node in order:
        left = max(0, gains.get(id(node[1]), 0))
        right = max(0, gains.get(id(node[2]), 0))
        through = node[0] + left + right
        if best[0] is None or through > best[0]:
            best[0] = through
        gains[id(node)] = node[0] + max(left, right)
    return best[0]

def tree_mirror_invert(root):
    """A new tree with every left and right child swapped.

    The input tree is not mutated."""
    fail = make_fail("tree_mirror_invert")
    _tree(fail, root)
    clone = [root[0], None, None]
    stack = [(root, clone)]
    while stack:
        src, dst = stack.pop()
        left, right = src[1], src[2]
        if right is not None:
            dst[1] = [right[0], None, None]
            stack.append((right, dst[1]))
        if left is not None:
            dst[2] = [left[0], None, None]
            stack.append((left, dst[2]))
    return clone

def tree_complete_check(root):
    """True when every level is full except possibly the last,
    which fills left to right.

    Level-order with a head cursor: once a missing child slot is
    seen, every later slot must be empty. The queue holds at most
    twice the validated node count plus one slot."""
    fail = make_fail("tree_complete_check")
    _tree(fail, root)
    queue = [root]
    head = 0
    gap = False
    while head < len(queue):
        node = queue[head]
        head += 1
        if node is None:
            gap = True
            continue
        if gap:
            return False
        queue.append(node[1])
        queue.append(node[2])
    return True

def tree_lowest_common_ancestor(root, value_a, value_b):
    """Value of the deepest node holding both query values below it.

    Values in the tree must be unique; a node counts as its own
    ancestor, so when one query value sits under the other the
    higher one answers. Refuses when either value is absent."""
    fail = make_fail("tree_lowest_common_ancestor")
    _tree(fail, root, unique=True)
    check_int(fail, value_a, "value_a")
    check_int(fail, value_b, "value_b")
    parent = {id(root): None}
    found = {}
    queue = [root]
    while queue:
        node = queue.pop()
        if node[0] == value_a:
            found["a"] = node
        if node[0] == value_b:
            found["b"] = node
        for child in (node[1], node[2]):
            if child is not None:
                parent[id(child)] = node
                queue.append(child)
    if "a" not in found:
        fail("missing:value_a")
    if "b" not in found:
        fail("missing:value_b")
    seen = set()
    node = found["a"]
    while node is not None:
        seen.add(id(node))
        node = parent[id(node)]
    node = found["b"]
    while id(node) not in seen:
        node = parent[id(node)]
    return node[0]

def tree_level_sums_max(root):
    """Largest sum of the values on any single depth level.

    The root alone is level one."""
    fail = make_fail("tree_level_sums_max")
    _tree(fail, root)
    best = None
    level = [root]
    while level:
        total = sum(node[0] for node in level)
        if best is None or total > best:
            best = total
        nxt = []
        for node in level:
            for child in (node[1], node[2]):
                if child is not None:
                    nxt.append(child)
        level = nxt
    return best

def tree_right_side_view(root):
    """Values visible from the right: the last node of every level,
    top to bottom."""
    fail = make_fail("tree_right_side_view")
    _tree(fail, root)
    view = []
    level = [root]
    while level:
        view.append(level[-1][0])
        nxt = []
        for node in level:
            for child in (node[1], node[2]):
                if child is not None:
                    nxt.append(child)
        level = nxt
    return view
