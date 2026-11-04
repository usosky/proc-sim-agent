PASS if the answer identifies these problems and gives corrected code:
- statements must start in column 7 (six spaces); the first line starts in column 1;
- tabs are not allowed (second line);
- text beyond column 72 is ignored, so the long third line must be continued (a character in
  column 6 of the next line) or shortened;
- an Import variable (TR) must not be assigned: copy imports to local variables first (e.g.
  TL = TR) and guard the copy (this is the READ-VAR warning, ADFORT.7);
- the corrected code is fixed-form, uses the local copies, and keeps XOUT as the exported result.
It should also point out that names such as AK, EA, TAU and the pressure-correction terms must be
defined (Define sheet) or set in the code, otherwise they start as zero.

FAIL if it misses the import-assignment problem or returns code that still has a tab, a statement
before column 7, or a line past column 72.
