# M20 Row 108 Choice Architecture contract

Ledger pin: id 108, title "Choice Architecture", description verbatim "Organizes options to influence decisions".

Purpose: an ethical-use, transparent review of how a set of options is presented. It checks structure from supplied declarations. It does not predict choices, claim any effect on decisions, or give advice. Wording in the ledger about influence is not implemented as a covert effect; presentation must stay disclosed and easy to opt out of.

Delta against the existing mechanism `_choice_architecture` in `negotiation_behavior_0085_0109.py` (card line 572; line number not re-read):
- Existing: dominated options by pairwise <=/<, float-style burden units, shortlist min(5, n), allowed from easy/transparent/visible/default-not-dominated, +/-1 interval.
- New: exact dominance (all attributes >=, at least one >) over integer attributes, first dominator in option order named, Pareto front, burden = options x attributes, over-choice flag above 7 options, failures named in fixed order (default_dominated, opt_out_not_easy, not_transparent, alternatives_hidden), allowed only with no failures. No shortlist, no interval.

Input keys (exactly): options, default, attributes, easy_opt_out, transparent, alternatives_visible. Options 2 to 20 unique texts of at most 100 chars; attributes 1 to 10 integers per option, same count, absolute value at most 1000000, no bools. Flags must be bool.
Refusals: ChoiceError with prefix "CHOICE108: ". Output carries three fixed limits strings.
New files only: choice_architecture108.py, test_m20_choice_architecture108.py, this document. Pure stdlib, no I/O.
