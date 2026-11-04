PASS if the answer:
- reads the files in v0.04 itself (it does not ask for pasted tables), and checks that the .his
  and .rep come from the same run (they do: the .his is stamped at the start of the run, the .rep
  when the report is written at its end, 38 s later); it may ask for the .bkp, which is not in the
  folder;
- gives a table with the items, expected values, model values and a verdict per item (pass, fail
  or missing), from the report, with: the product temperature failing (40 C in the report against
  45 C expected), the make-up water missing (there is no MAKEUP stream in the report), and the mass
  balance, CO2 and R1 duty items passing;
- says what to check or fix for the failed and missing items (for example the step's temperature
  setting and whether the MAKEUP stream was added and connected), and what to send next time.

FAIL if it says the step passed, invents values that are not in the files, or does not notice the
missing stream.
