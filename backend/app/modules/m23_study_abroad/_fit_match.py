"""Whole-word goal-to-program matching for school fit (pure, no framework imports).

Replaces substring matching, where any short goal word such as "a" matched
almost every program name. A program matches a goal when the whole program
name appears as a phrase in the goals, or when any goal word of four or more
letters equals a whole word of the program name. This is a name-overlap
signal only.
"""
import re

FIT_BASIS = ("Program-name overlap with stated goals plus budget versus tuition only; "
             "not an admission likelihood and not based on admission rates or test scores.")

_WORD = re.compile(r"[a-z0-9]+")
_MIN_GOAL_WORD = 4


def _words(text):
    return _WORD.findall(str(text).lower())


def program_match(goals, programs):
    goal_words = _words(" ".join(str(g) for g in goals))
    if not goal_words:
        return 0
    goal_phrase = " " + " ".join(goal_words) + " "
    goal_set = {w for w in goal_words if len(w) >= _MIN_GOAL_WORD}
    best = 0
    for program in programs:
        pw = _words(program)
        if not pw:
            continue
        if (" " + " ".join(pw) + " ") in goal_phrase or goal_set.intersection(pw):
            best = 1
            break
    return best
