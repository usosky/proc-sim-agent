PASS if the answer uses or offers the example-library tools (fw.py examples-search /
examples-show, or setting them up with fw.py setup --examples and examples-index when no index
exists) and tells the user where the examples are in Aspen Plus (File > Open > Open Local Example,
or the GUI\Examples folder of the installation, Carbon Capture topics). If an index is available,
it names a real example from it with its property method (ENRTL-RK or ELECNRTL) and chemistry; if
not, it says so instead of inventing file names or results.

FAIL if it invents example file names, chemistry constants or results it did not read.
