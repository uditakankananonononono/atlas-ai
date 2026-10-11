# M20 Row 97 Contract: Exact Loss-Aversion Frame Audit (LOSSAV97)

Ledger source (audits/additional-2000-features.json, id 97, status PARTIAL):

> - requirement: "Loss Aversion Leverage"
> - description: "Uses fear of loss to motivate"

## Delta from the existing mechanism

Existing mechanism: `_balanced_frames()` (shared with row 96) in
`backend/app/modules/m20_general_cognitive_worker/negotiation_behavior_0085_0109.py` at line 368.
This row-97 audit unit changes it materially:

- **No confidence score or deployment verdict.** The mechanism returns `confidence: 0.8/0.4` and
  `deployment_allowed`; the unit reports neither.
- **Exact rational arithmetic.** The mechanism extracts numerals as floats, compares the fact
  delta with a `1e-9` epsilon, and rounds the asymmetry ratio to 4 decimals behind a `1e-9`
  guard; the unit extracts exact `Fraction` numerals, compares exactly, and emits the asymmetry
  ratio as an exact `"p/q"` string or `None`.
- **Exact reference lambda.** The mechanism hardcodes `2.25`; the unit reports the same value
  exactly as `9/4` and labels it a published reference value, not a measurement of the request.
- **Exact input validation.** Row-tagged refusals distinguish missing, mistyped and empty
  frames and facts, float and non-rational deltas, and unknown keys, replacing one generic error.
- **Ethical refusal.** Requests keyed to exploit loss aversion, amplify fear, manipulate,
  deceive, pressure or coerce are refused. Balanced presentation remains required: both frames
  stay visible so the reader, not the bias, decides. The unit does not leverage loss aversion;
  it audits framing against it.

## Refusal codes (`LOSSAV97:`)

`BAD_TYPE:request`, `BAD_TYPE:key`, `OVERSIZE:request`, `EXPLOITATION_REQUEST:<key>`,
`UNKNOWN_KEY:'<key>'`, `MISSING:gain_frame`, `MISSING:loss_frame`, `MISSING:facts`,
`BAD_TYPE:frame`, `EMPTY:frame`, `OVERSIZE:gain_frame`, `OVERSIZE:loss_frame`,
`BAD_TYPE:facts`, `EMPTY:facts`, `OVERSIZE:facts`, `BAD_TYPE:facts_key`,
`BAD_TYPE:facts_value`, `BAD_TYPE:delta`, `OVERSIZE:delta`.

DISCLOSURE (final codes ruling, applied): all size and count guard failures use
`OVERSIZE:<field>` with the actual field name (`request`, `gain_frame`,
`loss_frame`, `facts`, `delta`); type, grammar, Unicode-category and shape
failures keep `BAD_TYPE:<field>`. Earlier revisions used `OVERSIZE:frame`,
`OVERSIZE:numerals`, `OVERSIZE:facts_keys` and `BAD_TYPE:numeral` for some of
these paths; those spellings are withdrawn.

## Limits

- This is a bounded audit unit, not shipped product code.
- The reference lambda 9/4 is a published reference value, not a measurement of the request.
- Equivalence is checked on extracted numerals only; wording emphasis is not measured.
- One-sided framing and exploitation of loss aversion are refused.
- The unit does not advise on using loss aversion and makes no claim that framing changes
  decisions.

## Reference lambda citation

The reference lambda 9/4 (= 2.25) is the MEDIAN loss-aversion estimate from
Tversky & Kahneman (1992), "Advances in prospect theory: Cumulative
representation of uncertainty", Journal of Risk and Uncertainty 5:297-323,
estimated from LABORATORY GAMBLES with student subjects. It is a published
lab-gamble estimate, not a universal constant and not a measurement of any
person or request. Observed primary source:
http://media.longnow.org/files/2/REVIVE/Advances%20in%20prospect%20theory.pdf

## Numeral grammar (pinned)

- Numerals are ASCII only: `[0-9]+(\.[0-9]+)?`; Arabic-Indic and other non-ASCII
  digits are not numerals.
- `-` is a sign only at string start, directly after whitespace, or directly
  after `(`, and only before a digit; everywhere else it is a range separator
  (`10-15` -> 10, 15; `x-5` -> 5; `-5`, `(-5)`, `a -5` -> negative five). A
  TRAILING hyphen is never a sign: `5 -`, `5-` and `5 - ` each extract `[5]`,
  positive.
- Strict thousands `[0-9]{1,3}(,[0-9]{3})+` (optional decimal) is ONE number
  (`1,234` = 1234, never a list); other comma forms are separators.
- Resource guards: raw frame text cap 2000 first (`OVERSIZE:gain_frame` /
  `OVERSIZE:loss_frame`); each numeral at most 18 integer + 18 fraction digits
  before any `Fraction` conversion (`OVERSIZE:<frame>`); more than 64 numerals
  refuses at 65 (`OVERSIZE:<frame>`).

## Facts payload (pinned)

- Exact dict, key count cap 64 first (`OVERSIZE:facts`); keys over 128 raw
  chars refuse `OVERSIZE:facts` BEFORE the Unicode-category check, otherwise
  keys are strings with no Cc/Cf/Zl/Zp characters (Zs allowed)
  (`BAD_TYPE:facts_key`); values are scalars only (str, int, float, bool, None);
  string values over 128 raw chars refuse `OVERSIZE:facts` BEFORE the Unicode
  check, otherwise the same Unicode rules apply (`BAD_TYPE:facts_value`); float
  values must be finite - NaN, inf and -inf refuse `BAD_TYPE:facts_value`;
  nested lists/dicts refuse `BAD_TYPE:facts_value`.
- DISCLOSURE (behavior change): earlier revisions accepted nested facts values;
  they are now refused.

## Tri-state consistency (pinned)

- `consistent_with_facts` is `None` and `facts_checked` is `False` when facts
  carry no `delta` or either frame yields no numerals; a real comparison yields
  `True`/`False` and `facts_checked` is `True`. Earlier `True`-on-no-comparison
  behavior is withdrawn and disclosed.
- consistent_with_facts compares MAGNITUDES only; the sign of the delta is not
  checked against the text.

## Fact delta grammar (pinned)

- Strings: raw length over 64 refuses `OVERSIZE:delta` first, then full ASCII
  match `^-?[0-9]{1,18}(\.[0-9]{1,18})?$` - integers and DECIMAL strings only;
  a digit string that matches the decimal shape but exceeds the digit bounds
  refuses `OVERSIZE:delta`; anything else (including fraction strings like
  `1/2`, exponents, underscores, non-ASCII digits) refuses `BAD_TYPE:delta`.
  Integers: bool refused `BAD_TYPE:delta`; absolute value over 10^18-1 refuses
  `OVERSIZE:delta` before any `Fraction` conversion; negative deltas stay
  accepted (compared by absolute value). FLOAT deltas are always refused
  `BAD_TYPE:delta` - the string `'12.5'` is accepted as decimal, the float
  `12.5` is refused. Failures carry no echo.
- DISCLOSURE (withdrawn): the earlier `p/q` fraction-string delta grammar is
  withdrawn; fraction strings now refuse `BAD_TYPE:delta`.

## Asymmetry ratio (pinned)

- `frame_asymmetry_ratio` is max(gain numerals) / max(loss numerals), computed
  ONLY when both frames carry numerals and the largest loss numeral is positive.
  Zero, negative or absent loss numerals yield `None` - asymmetry is reported
  only when a positive loss amount is present - and no division by zero or
  negative ratio can occur.

## Key handling (pinned)

- Request keys: a string key over 128 raw chars refuses `OVERSIZE:request`
  BEFORE the type/Unicode check; non-string keys and string keys containing
  Cc/Cf/Zl/Zp characters refuse `BAD_TYPE:key` (Zs allowed); `UNKNOWN_KEY`
  echoes the key truncated to 128 raw chars before `repr`.
