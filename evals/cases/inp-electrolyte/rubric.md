PASS if a file caustic_absorber.inp was written (or its full text given) and it contains:
IN-UNITS; DATABANKS; COMPONENTS with H2O, CO2, N2, NAOH (or NA+ and OH- feed basis) and the
ions H3O+, OH-, HCO3-, CO3-2 (or CO3--) and NA+; HENRY-COMPS with CO2 (and N2); a CHEMISTRY
paragraph with water, CO2/bicarbonate and bicarbonate/carbonate equilibria and NaOH dissociation;
a PROPERTIES statement with an electrolyte method (ELECNRTL or ENRTL-RK) using that chemistry with
TRUE-COMPS=YES; a RADFRAC absorber with CONDENSER=NONE and REBOILER=NONE, liquid fed on top and gas
at the bottom; feed STREAM paragraphs with two state variables and flows; a pH property in the
report (PROP-SET with PH). The answer says how to open it (File > Open, Input Files) and that it
was checked (inp-check) or what to check after the first run.

FAIL if the chemistry is missing, the apparent-component approach is used, the column has a
condenser or reboiler with no specifications, or the file would clearly not parse (statements in
column 1, missing FLOWSHEET connectivity).
