PASS if the answer does all of the following:
- frames the job: the goal or KPI (NH3 in the stripped water below 50 ppmw) and how it will be
  checked, and the reference data or basis it needs from the user or assumes explicitly;
- proposes a staged build in which the components and property method come first (an
  electrolyte method such as ELECNRTL or ENRTL-RK with chemistry for NH3/H2S/H2O ionisation, the
  true-component approach because NH3 and H2S are volatile, Henry components) and each stage has a
  concrete check or pass criterion before the next one starts;
- starts the simplest way (for example a flash or a short column before tuning the full column)
  rather than asking the user to build the whole flowsheet at once;
- gives concrete first steps for stage 1 (click paths or an input file) and says what result to
  send back.

FAIL if it delivers a complete final column model with no checkpoints, uses the apparent-component
approach for this system, or skips checking the property model.
