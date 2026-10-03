"""Synthetic test data: a tiny MadCap WebHelp tree and small Aspen-style run files.

Everything here is invented for the tests (no vendor content); the layouts copy the file
formats that the parsers read.
"""
from __future__ import annotations

from pathlib import Path

# ---------------------------------------------------------------------------
# MadCap WebHelp
# ---------------------------------------------------------------------------
_TOPIC = """<!DOCTYPE html>
<html xmlns:MadCap="http://www.madcapsoftware.com/Schemas/MadCap.xsd" lang="en-us" data-mc-toc-path="{crumb}">
<head><meta charset="utf-8" /><title>{title}</title></head>
<body>
<h1>{title}</h1>
{body}
</body>
</html>
"""

_BOOKS = {
    "demoblock": {
        "toc_path": "Using the Simulation Environment|Blocks",
        "topics": {
            "working_with_reactor.htm": ("Working with DemoReactor", "DemoReactor",
                                         "<p>Use DemoReactor when the stoichiometry is known and kinetics are not.</p>"
                                         '<p>See <a href="reactor_setup.htm">DemoReactor Setup Sheet</a>.</p>'),
            "reactor_setup.htm": ("DemoReactor Setup Sheet", "DemoReactor|DemoReactor Setup Form",
                                  "<p>Specify the outlet temperature and the fractional conversion.</p>"
                                  "<ul><li>Temperature</li><li>Pressure (zero or negative means a pressure drop)</li></ul>"
                                  "<table><tr><th>Field</th><th>Meaning</th></tr>"
                                  "<tr><td>Conversion</td><td>fraction of the key component converted</td></tr></table>"
                                  '<p><img src="../GeneratedImages/Equations/Equation1.svg" alt="" /></p>'),
            "reactor_results.htm": ("DemoReactor Results Sheet", "DemoReactor|DemoReactor Results Form",
                                    "<p>Shows the heat duty and the outlet vapor fraction.</p>"),
        },
        "aliases": {"reactor_setup": ("reactor_setup.htm", "830001")},
    },
    "democonv": {
        "toc_path": "Using the Simulation Environment|Convergence",
        "topics": {
            "secant_method.htm": ("Secant Method", "Convergence|Methods",
                                  "<p>Secant converges single design specifications. Select the bracketing option "
                                  "when the function is flat over a region; Check Bounds also tries the other bound.</p>"),
            "tear_convergence.htm": ("Tear Convergence Sheet", "Convergence|Options",
                                     "<p>Set the tear stream tolerance and the trace threshold.</p>"),
        },
        "aliases": {"secant_method": ("secant_method.htm", "910010")},
    },
}

_EQUATION_SVG = """<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink">
<defs id="MathJax_SVG_glyphs"><path id="MJMATHI-58" d=""/><path id="MJMAIN-3D" d=""/><path id="MJMATHI-47" d=""/></defs>
<g><use xlink:href="#MJMATHI-58"/><use xlink:href="#MJMAIN-3D"/><use xlink:href="#MJMATHI-47"/>
<use xlink:href="#MJMAIN-28"/><use xlink:href="#MJMATHI-58"/><use xlink:href="#MJMAIN-29"/></g></svg>
"""


def _js_entries(entries):
    return ",".join(f"'{url}':{{i:[{i}],t:['{t}'],b:['']}}" for url, i, t in entries)


def make_help(root: Path) -> Path:
    """Write a 2-book help system under root and return root."""
    root.mkdir(parents=True, exist_ok=True)
    subs = "\n".join(f'    <Url Source="Subsystems/{b}/{b}.mcwebhelp" TocPath="{spec["toc_path"]}" />'
                     for b, spec in _BOOKS.items())
    (root / "apwn.mcwebhelp").write_text(
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<WebHelpSystem DefaultUrl="Content/html/welcome.htm" Toc="Data/Tocs/apwn.js" Alias="Data/Alias.xml" '
        'BuildTime="1/1/2026 1:00:00 PM">\n  <Subsystems>\n' + subs + "\n  </Subsystems>\n</WebHelpSystem>\n",
        encoding="utf-8")
    data = root / "Data"
    (data / "Tocs").mkdir(parents=True, exist_ok=True)
    (data / "Tocs" / "apwn.js").write_text(
        "define({numchunks:1,prefix:'apwn_Chunk',chunkstart:['___'],tree:{n:[{i:0,c:1,n:[{i:1,c:0},"
        "{i:2,c:0},{i:3,r:1,m:0,c:0},{i:4,r:1,m:1,c:0}]}]}});", encoding="utf-8")
    (data / "Tocs" / "apwn_Chunk0.js").write_text(
        "define({" + _js_entries([("___", 0, "Demo Help"), ("/Content/html/welcome.htm", 1, "Welcome"),
                                 ("/Content/html/whatsnew.htm", 2, "What\\u0027s New in Demo Plus V15"),
                                 ("/../x/demoblock/demoblock.flprj", 3, "demoblock.chm::/demoblock.hhc"),
                                 ("/../x/democonv/democonv.flprj", 4, "Convergence")]) + "});",
        encoding="utf-8")
    (data / "SearchTopic_Chunk0.js").write_text(
        'define({"0":{y:0,u:"../Content/html/welcome.htm",l:-1,t:"Welcome",i:0.1,a:"Welcome to the demo help."}});',
        encoding="utf-8")
    (data / "Alias.xml").write_text('<?xml version="1.0" encoding="utf-8"?>\n<CatapultAliasFile Version="1">\n'
                                    '<Map Name="welcome" Link="html/welcome.htm" ResolvedId="1000" />\n'
                                    "</CatapultAliasFile>\n", encoding="utf-8")
    html = root / "Content" / "html"
    html.mkdir(parents=True, exist_ok=True)
    (html / "welcome.htm").write_text(_TOPIC.format(title="Welcome", crumb="Welcome",
                                                    body="<p>Welcome to the demo help.</p>"), encoding="utf-8")
    (html / "whatsnew.htm").write_text(_TOPIC.format(title="What's New in Demo Plus V15", crumb="Welcome",
                                                     body="<p>New features.</p>"), encoding="utf-8")

    for b, spec in _BOOKS.items():
        bdir = root / "Subsystems" / b
        (bdir / "Data" / "Tocs").mkdir(parents=True, exist_ok=True)
        (bdir / "Content" / "html").mkdir(parents=True, exist_ok=True)
        (bdir / f"{b}.mcwebhelp").write_text(
            '<?xml version="1.0" encoding="utf-8"?>\n'
            f'<WebHelpSystem Toc="Data/Tocs/{b}.js" BuildTime="1/1/2026 1:00:00 PM"></WebHelpSystem>\n',
            encoding="utf-8")
        names = list(spec["topics"])
        tree = "{i:0,c:0,n:[" + ",".join(f"{{i:{k},c:0}}" for k in range(1, len(names))) + "]}"
        (bdir / "Data" / "Tocs" / f"{b}.js").write_text(
            f"define({{numchunks:1,prefix:'{b}_Chunk',chunkstart:['/Content/html/{names[0]}'],tree:{{n:[{tree}]}}}});",
            encoding="utf-8")
        (bdir / "Data" / "Tocs" / f"{b}_Chunk0.js").write_text(
            "define({" + _js_entries([(f"/Content/html/{n}", k, spec["topics"][n][0]) for k, n in enumerate(names)])
            + "});", encoding="utf-8")
        cat = ",".join(f'"{k}":{{y:0,u:"../Content/html/{n}",l:-1,t:"{spec["topics"][n][0]}",i:0.1,a:"abstract {k}"}}'
                       for k, n in enumerate(names))
        (bdir / "Data" / "SearchTopic_Chunk0.js").write_text("define({" + cat + "});", encoding="utf-8")
        (bdir / "Data" / "SearchUrl_Chunk0.js").write_text("define({});", encoding="utf-8")
        maps = "\n".join(f'<Map Name="{a}" Link="html/{f}" ResolvedId="{rid}" />'
                         for a, (f, rid) in spec["aliases"].items())
        (bdir / "Data" / "Alias.xml").write_text('<?xml version="1.0" encoding="utf-8"?>\n<CatapultAliasFile Version="1">\n'
                                                 + maps + "\n</CatapultAliasFile>\n", encoding="utf-8")
        for n, (title, crumb, body) in spec["topics"].items():
            (bdir / "Content" / "html" / n).write_text(_TOPIC.format(title=title, crumb=crumb, body=body),
                                                       encoding="utf-8")
    eq = root / "Subsystems" / "demoblock" / "Content" / "GeneratedImages" / "Equations"
    eq.mkdir(parents=True, exist_ok=True)
    (eq / "Equation1.svg").write_text(_EQUATION_SVG, encoding="utf-8")
    return root


# ---------------------------------------------------------------------------
# run files (invented flowsheet: MIX1 -> R1 -> SPLIT with recycle)
# ---------------------------------------------------------------------------
HIS = r"""
 PLATFORM: WIN-X64                                       MARCH 3, 2026
 VERSION: 41.0   Build 609                               TUESDAY
 INSTALLATION:                                           10:15:02 A.M.

 THIS COPY OF ASPEN PLUS LICENSED TO ACME TEST CORP

 *** INPUT SUMMARY ***

 >>CURRENT RUN

   ORIGINAL RUN                           MARCH 3, 2026
   10:15:02 A.M.                          TUESDAY
   INPUT FILE: _1234abc.inm
   RUN ID : _1234abc
          1    ;
          2    ;Input file created by Aspen Plus Rel. 41.0 at 10:15:01 Tue Mar 3, 2026
          3    ;Directory C:\Users\jdoe\Projects\demo  Runid DEMO
          4    ;
          5
          6    IN-UNITS MET PRESSURE=bar TEMPERATURE=C
          7
          8    DATABANKS 'APV150 PURE39'
          9
         10    COMPONENTS
         11        CO2 CO2 /
         12        H2O H2O /
         13        N2 N2
         14
         15    FLOWSHEET
         16        BLOCK MIX1 IN=FEED RECYCLE OUT=S1
         17        BLOCK R1 IN=S1 OUT=S2
         18        BLOCK SPLIT IN=S2 OUT=PROD RECYCLE
         19
         20    PROPERTIES PENG-ROB
         21
         22    STREAM FEED
         23        SUBSTREAM MIXED TEMP=25. PRES=1.01325  &
         24            MOLE-FLOW=100.
         25        MOLE-FRAC CO2 0.1 / H2O 0.05 / N2 0.85
         26
         27    BLOCK MIX1 MIXER
         28        PARAM
         29
         30    BLOCK SPLIT FSPLIT
         31        FRAC RECYCLE 0.3
         32
         33    BLOCK R1 RSTOIC
         34        PARAM TEMP=40. PRES=0.
         35        STOIC 1 MIXED CO2 -1. / H2O 1.
         36        CONV 1 MIXED CO2 0.9
         37
         38    CALCULATOR CAP
         39        DEFINE FCO2 MOLE-FLOW STREAM=S1 SUBSTREAM=MIXED  &
         40            COMPONENT=CO2 UOM="kmol/hr"
         41        DEFINE XCONV BLOCK-VAR BLOCK=R1 VARIABLE=CONV  &
         42            SENTENCE=CONV ID1=1
         43        DEFINE TIN STREAM-VAR STREAM=S1 SUBSTREAM=MIXED  &
         44            VARIABLE=TEMP UOM="K"
         45        DEFINE FN2 MOLE-FLOW STREAM=S1 SUBSTREAM=MIXED  &
         46            COMPONENT=N2 UOM="kmol/hr"
         47    C     cap the conversion at what is available
         48    F     IF (TIN .LT. 200.0D0) TIN = 298.15D0
         49    F     XCONV = 0.9D0 * FACTOR
         50    F     XCONV = XCONV + 0.0D0 * FCO2 * TIN + 0.0D0 * 1.0D0 * 2.0D0 * 3.0D0 * 4.0D0
         51        READ-VARS FCO2 TIN FN2
         52        WRITE-VARS XCONV
         53
         54    DESIGN-SPEC DS1
         55        DEFINE FPROD MOLE-FLOW STREAM=PROD SUBSTREAM=MIXED  &
         56            COMPONENT=CO2 UOM="kmol/hr"
         57        SPEC "FPROD" TO "1.0"
         58        TOL-SPEC "0.01"
         59        VARY BLOCK-VAR BLOCK=SPLIT SENTENCE=FRAC VARIABLE=FRAC  &
         60            ID1=RECYCLE
         61        LIMITS "0.1" "0.9"
         62
         63    DISABLE
         64        DESIGN-SPEC DS1
         65
 *** INPUT TRANSLATOR MESSAGES ***

  *   WARNING IN PHYSICAL PROPERTY SYSTEM                      (PDATAFAP.1)
      THE FOLLOWING CONVENTIONAL COMPONENTS WERE NOT IN A DATA BANK.
      CHECK DATA BANK NAMES FOR SPELLING.

      INFORMATION                                              (PSTOP1AP.1)
      THERE ARE HENRY COMPONENTS DEFINED IN THIS CASE, THE BINARY DATABANK
      WILL BE SEARCHED AUTOMATICALLY FOR ANY AVAILABLE HENRY CONSTANTS.

 *** CALCULATION TRACE ***


 *** FLOWSHEET ANALYSIS MESSAGES ***

  *   WARNING DURING FLOWSHEET ANALYSIS                        (ADFORT.7)
      FORTRAN READ-VAR TIN IN FORTRAN BLOCK CAP
      APPEARS ON THE LEFT-HAND SIDE OF AN ASSIGNMENT STATEMENT.

      BLOCK $OLVER01 (METHOD: WEGSTEIN) HAS BEEN DEFINED TO CONVERGE
               STREAMS: RECYCLE

      COMPUTATION ORDER FOR THE FLOWSHEET IS:
      $OLVER01 MIX1 CAP R1 SPLIT
      (RETURN $OLVER01)

Calculations begin                                                              time      0.10


 SIMULATION CALCULATIONS BEGIN                                                    TIME =      0.10

      CONVERGENCE BLOCK $OLVER01  METHOD: WEGSTEIN                                TIME =      0.10
      ITER   0 For Tear Streams: RECYCLE

      UOS BLOCK MIX1     MODEL: MIXER                                             TIME =      0.10
      KODE = 2  NTRIAL =   1  T = 298.1500  P =  101325.      V =  1.00000      Q =  0.00000

      CALCULATOR BLOCK CAP                                                        TIME =      0.10

      UOS BLOCK R1       MODEL: RSTOIC                                            TIME =      0.10

  *   WARNING WHILE EXECUTING UNIT OPERATIONS BLOCK: "R1" (MODEL: "RSTOIC")
                                                               (URE07.3)
      COMPONENT "CO2" HAS ZERO FLOWRATE IN THE OUTLET STREAM.
      FRACTIONAL CONVERSION HAS BEEN MODIFIED BY
      A FACTOR OF "0.9500000"
      KODE = 2  NTRIAL =   3  T = 313.1500  P =  101325.      V =  1.00000      Q = -12345.6

      UOS BLOCK SPLIT    MODEL: FSPLIT                                            TIME =      0.11

      CONVERGENCE BLOCK $OLVER01  METHOD: WEGSTEIN                                TIME =      0.11
      ITER   1 For Tear Streams: RECYCLE

  LOOP $OLVER01 ITER    1:   3 VARS NOT CONVERGED, MAX ERR/TOL      120.50        TIME =      0.11

      UOS BLOCK MIX1     MODEL: MIXER                                             TIME =      0.11
      KODE = 2  NTRIAL =   1  T = 300.1500  P =  101325.      V =  1.00000      Q =  0.00000

      CALCULATOR BLOCK CAP                                                        TIME =      0.11

      UOS BLOCK R1       MODEL: RSTOIC                                            TIME =      0.11
      KODE = 2  NTRIAL =   3  T = 313.1500  P =  101325.      V =  1.00000      Q = -15000.0

      UOS BLOCK SPLIT    MODEL: FSPLIT                                            TIME =      0.12

      CONVERGENCE BLOCK $OLVER01  METHOD: WEGSTEIN                                TIME =      0.12
      ITER   2 For Tear Streams: RECYCLE

  LOOP $OLVER01 ITER    2:     *** CONVERGED *** , MAX ERR/TOL      0.5000        TIME =      0.12

 Report Writer entered                                                            Time =      0.13

 Results generated                                                                Time =      0.14

RUN SAVED



 *** SUMMARY OF ERRORS ***

                  PHYSICAL
                  PROPERTY  SYSTEM  SIMULATION
 TERMINAL ERRORS      0        0         0
   SEVERE ERRORS      0        0         0
          ERRORS      0        0         0
        WARNINGS      1        0         1
"""

# version 2: one input change (split fraction), for his-diff
HIS_V2 = HIS.replace("FRAC RECYCLE 0.3", "FRAC RECYCLE 0.4")


def write(path: Path, text: str, crlf: bool = True) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = text.lstrip("\n")
    if crlf:
        data = data.replace("\n", "\r\n")
    path.write_bytes(data.encode("latin-1"))
    return path


REP = (
    "\f ASPEN PLUS   PLAT: WIN-X64   VER: 41.0                   03/03/2026  PAGE 1\n"
    "\n"
    "                              RUN CONTROL SECTION\n"
    "\n"
    " RUN CONTROL INFORMATION\n"
    " -----------------------\n"
    "\n"
    " THIS COPY OF ASPEN PLUS LICENSED TO ACME TEST CORP\n"
    "\n"
    " TYPE OF RUN: NEW\n"
    "\n"
    " INPUT FILE NAME: _1234abc.inm\n"
    " CALLING PROGRAM NAME:          apmain\n"
    " LOCATED IN: C:\\Program Files\\AspenTech\\Aspen Plus V15.0\\Engine\\xeq\n"
    "\n"
    " SIMULATION REQUESTED FOR ENTIRE FLOWSHEET\n"
    "\f ASPEN PLUS   PLAT: WIN-X64   VER: 41.0                   03/03/2026  PAGE 2\n"
    "\n"
    "                               FLOWSHEET SECTION\n"
    "\n"
    "   TEAR STREAM SUMMARY\n"
    "   ===================\n"
    "\n"
    "   STREAM    VARIABLE         MAXIMUM      MAX. ERR.    ABSOLUTE          CONV\n"
    "   ID        ID               ERR/TOL      RELATIVE     ERROR       STAT  BLOCK\n"
    "   ------    --------         --------     -------      ---------   ----  -----\n"
    "   RECYCLE  CO2 MOLEFLOW       0.5000       0.5000E-04   0.1000E-04  #    $OLVER01\n"
    "\n"
    "   #  = CONVERGED\n"
    "   *  = NOT CONVERGED\n"
    "\n"
    " OVERALL FLOWSHEET BALANCE\n"
    " -------------------------\n"
    "\n"
    "                      ***  MASS AND ENERGY BALANCE  ***\n"
    "                              IN          OUT       GENERATION   RELATIVE DIFF.\n"
    "    TOTAL BALANCE\n"
    "       MOLE(KMOL/HR )         100.000       100.000       0.00000       0.00000\n"
    "       MASS(KG/HR   )         2823.40       2823.40                     0.161E-15\n"
    "       ENTHALPY(CAL/SEC )    -0.325000E+07 -0.326234E+07                0.379E-02\n"
    "\f ASPEN PLUS   PLAT: WIN-X64   VER: 41.0                   03/03/2026  PAGE 3\n"
    "\n"
    "                              U-O-S BLOCK SECTION\n"
    "\n"
    " BLOCK:  R1       MODEL: RSTOIC\n"
    " ------------------------------\n"
    "   INLET STREAM:          S1\n"
    "   OUTLET STREAM:         S2\n"
    "                      ***  MASS AND ENERGY BALANCE  ***\n"
    "                                    IN              OUT        RELATIVE DIFF.\n"
    "    TOTAL BALANCE\n"
    "       MOLE(KMOL/HR )            130.000         130.000         0.00000\n"
    "\n"
    "                           ***  RESULTS  ***\n"
    "   OUTLET TEMPERATURE    C                                      40.000\n"
    "   OUTLET PRESSURE       BAR                                     1.0133\n"
    "   HEAT DUTY             CAL/SEC                           -12,345.6\n"
    "   VAPOR FRACTION                                                1.0000\n"
    "\f ASPEN PLUS   PLAT: WIN-X64   VER: 41.0                   03/03/2026  PAGE 4\n"
    "\n"
    "                                 STREAM SECTION\n"
    "\n"
    " FEED PROD\n"
    " ---------\n"
    "\n"
    " STREAM ID               FEED       PROD\n"
    " FROM :                  ----       SPLIT\n"
    " TO   :                  MIX1       ----\n"
    "\n"
    " SUBSTREAM: MIXED\n"
    " PHASE:                  VAPOR      VAPOR\n"
    " COMPONENTS: KMOL/HR\n"
    "   CO2                   10.0000     1.0000\n"
    "   H2O                    5.0000    14.0000\n"
    "   N2                    85.0000    85.0000\n"
    " TOTAL FLOW:\n"
    "   KMOL/HR              100.0000   100.0000\n"
    "   KG/HR               2823.4000  2823.4000\n"
    " TEMPERATURE C            25.0000    40.0000\n"
    " PRESSURE    BAR           1.0133     1.0133\n"
    "\f ASPEN PLUS   PLAT: WIN-X64   VER: 41.0                   03/03/2026  PAGE 5\n"
    "\n"
    "                             PROBLEM STATUS SECTION\n"
    "\n"
    " BLOCK STATUS\n"
    " ------------\n"
    "\n"
    " ****************************************************************************\n"
    " *                                                                          *\n"
    " * Calculations were completed normally                                     *\n"
    " *                                                                          *\n"
    " ****************************************************************************\n"
)

CPM = """<< Run reinitialized 10:15:00 Tue Mar 3, 2026>>

->Processing input specifications ...

  *   WARNING IN PHYSICAL PROPERTY SYSTEM
      THE FOLLOWING CONVENTIONAL COMPONENTS WERE NOT IN A DATA BANK.

  Flowsheet Analysis :

 Block $OLVER01 (Method: WEGSTEIN) has been defined to converge
         streams: RECYCLE

 COMPUTATION ORDER FOR THE FLOWSHEET:
 $OLVER01 MIX1 CAP R1 SPLIT
 (RETURN $OLVER01)

->Calculations begin ...

> Beginning Convergence Loop $OLVER01 Method: WEGSTEIN
  Converging tear streams: RECYCLE

   Block: MIX1     Model: MIXER

   Calculator Block CAP

   Block: R1       Model: RSTOIC
  *   WARNING
      COMPONENT "CO2" HAS ZERO FLOWRATE IN THE OUTLET STREAM.
      FRACTIONAL CONVERSION HAS BEEN MODIFIED BY

   Block: SPLIT    Model: FSPLIT

> Loop $OLVER01 Method: WEGSTEIN     Iteration    1
  Converging tear streams: RECYCLE
   3 vars not converged, Max Err/Tol   0.12050E+03

> Loop $OLVER01 Method: WEGSTEIN     Iteration    2
  Converging tear streams: RECYCLE
# Converged              Max Err/Tol   0.50000E+00

->Simulation calculations completed ...

               ***  Summary of Simulation Errors  ***

                   Physical
                   Property         System        Simulation
  Terminal Errors      0               0               0
    Severe Errors      0               0               0
           Errors      0               0               0
         Warnings      1               0               1

->Generating results ...

<< Report exported 10:15:05 Tue Mar 3, 2026>>
"""
