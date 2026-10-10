# EVO-LIFE1988: finite Conway Life simulation

Targets row1988 Artificial Life only for bounded SCOPED acceptance. Actual Conway
B3/S23 finite cellular automaton, not the old supplied scalar mean-coupling toy.
No other COG/system/emergence/self-organization row closes automatically.
Production/OIDC route `/api/v1/api/modules/20/artificial-life/simulate`.

Supplied width/height and live_cells [x,y] pairs define a binary grid. Each step
synchronously reads the prior generation's eight Moore neighbors. Dead cells
with exactly3 live neighbors are born; live cells survive with2 or3; others die.
Fixed boundaries treat outside cells as dead; toroidal boundaries wrap both axes.
Dimensions>=3 keep wrapped neighbor positions distinct. No in-place/asynchronous
updates. Exact live-cell/birth/death sets, density/population and step indices are
retained; first repeated exact state reports its earliest seen index and period.
A finite-grid repeat is not open-ended evolution or biological reproduction.

Tests independently recompute every local update, births/deaths and both boundary
modes; known still life, blinker period2, lone-cell extinction, glider displacement
in4steps verify actual phenomena. Receipts are simulation state, not hidden
chain-of-thought. No independent world observation, trained life model, adaptive
agent, genotype, ecology, energy budget or claims of consciousness/aliveness.

Width/height exact integers3..128, steps1..1000 default4, boundary fixed(default)
or toroidal. Live coordinates must be exact nonboolean in-range integer pairs,
unique; empty universe allowed. (steps+1)*width*height<=200000 bounds retained
states and cell scan work. Validation refuses422. Deterministic supplied-state
execution, no seed/model/provider/spend/external I/O/persistence. Cells per step
are explicitly evaluated; no pattern-specific shortcut. Ledger unchanged until
independent acceptance. Residual: agent-based/biological/open-ended adaptive life,
evolution and unrestricted artificial-life systems not implemented.
