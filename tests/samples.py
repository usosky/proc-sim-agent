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


# ---------------------------------------------------------------------------
# v0.2: example-library models (.bkp / .apwz), input files (.inp), stream tables
# ---------------------------------------------------------------------------
_BKP_HEAD = """MM "41.0" FLAVOR "NO" VERSION "41.0" DATETIME "{date}" 
MACHINE "WIN-NT/VC"  ; 
startlibrary
version1
NumLibs = 1
Built-In
NumCats = 1
Separators
active
endlibrary
; 
"""

# Electrolyte demo: chemistry with an equilibrium and a dissociation, Henry components, a
# hierarchy block with its own property method, a calculator, a design spec, a tear stream, and
# two objects hidden with Hide/Reveal (one buffer ends with '\\@END_HIDEBUF', one without '@').
BKP_DEMO = _BKP_HEAD.format(date="Mon Oct  5 10:00:00 2026") + r"""3
>VERSION 0
MIX
Mixer
Built-In
MIXER
>VERSION 0
FL1
Flash2
Built-In
FLASH2
>VERSION 0
HB
Hierarchy
Built-In
HIERARCHY
? HIDE_BUFFER SENSITIVITY ? PASTE_ITEMS ? 1 LEVEL = 1 SENSITIVITY "S-OLD" 
CANPARAM = 1 USENAME = "S-OLD" \ 
? SENSITIVITY "S-OLD" ? \ TABULATE COLNO = 1 EXPR = "X" \ \@
END_HIDEBUF ? HIDE_BUFFER CONVERGENCE ? PASTE_ITEMS ? 1 LEVEL = 2 
CONVERGENCE BROYDEN "CV-OLD" CANPARAM = 1 USENAME = "CV-OLD" \ ? CONVERGENCE 
BROYDEN "CV-OLD" ? \ PARAM MAXIT = 50 \ 
END_HIDEBUF ? SETUP MAIN ? \ "RUN-CLASS" RUN-CLASS = FLOWSHEET \ \ SIMULATE 
INTERACTIVE = NO \ ? SETUP DESCRIPTION ? \ DESCRIPTION DESCRIP = ( 
"Demo absorber: carbon dioxide into a sodium chloride brine" 
"with bicarbonate chemistry" ) \ ? COMPONENTS MAIN ? \ COMPONENTS CID = H2O 
ANAME = H2O OUTNAME = H2O DBNAME1 = "WATER" ANAME1 = "H2O" /  CID = CO2 ANAME = 
CO2 OUTNAME = CO2 DBNAME1 = "CARBON-DIOXIDE" ANAME1 = "CO2" /  CID = NACL ANAME 
= NACL OUTNAME = NACL DBNAME1 = "SODIUM-CHLORIDE" ANAME1 = "NACL" /  CID = 
"H3O+" ANAME = H3O+ OUTNAME = "H3O+" DBNAME1 = "H3O+" ANAME1 = "H3O+" /  CID = 
"HCO3-" ANAME = HCO3- OUTNAME = "HCO3-" DBNAME1 = "HCO3-" ANAME1 = "HCO3-" /  
CID = "NA+" ANAME = NA+ OUTNAME = "NA+" DBNAME1 = "NA+" ANAME1 = "NA+" /  CID = 
"CL-" ANAME = CL- OUTNAME = "CL-" DBNAME1 = "CL-" ANAME1 = "CL-" \ ? COMPONENTS 
"HENRY-COMPS" GLOBAL ? \ "HENRY-COMPS" CID = ( CO2 ) \ ? CHEMISTRY "C-1" ? ; 
"METCBAR_MOLE" ; \ STOIC REACNO = 1 STOIC-CID = CO2 COEF = -1. <0> <0> /  
REACNO = 1 STOIC-CID = H2O COEF = -2. <0> <0> \ \ STOIC1 REACNO1 = 1 STOIC-CID1 
= "HCO3-" COEF1 = 1. <0> <0> /  REACNO1 = 1 STOIC-CID1 = "H3O+" COEF1 = 1. <0> 
<0> \ \ K-STOIC K-S-REACNO = 1 A = 231.465 <0> <0> B = -12092.1 <0> <0> C = 
-36.7816 <0> <0> \ \ DISS ELECID = NACL DISS-CID = "NA+" DISS-COEF = 1. <0> <0> 
/  ELECID = NACL DISS-CID = "CL-" DISS-COEF = 1. <0> <0> \ ? PROPERTIES MAIN ? 
\ GPROPERTIES GPPROCTYPE = ALL GBASEOPSET = ELECNRTL GOPSETNAME = ELECNRTL GHEN 
= GLOBAL GCHEMISTRY = "C-1" GTRUE-COMPS = YES \ ? PROPERTIES "HB.MAIN" ? \ 
GPROPERTIES GBASEOPSET = "ENRTL-RK" \ ? FLOWSHEET GLOBAL ? \ BLOCK BLKID = MIX 
BLKTYPE = "MIXER" MDLTYPE = "Mixer" IN = ( FEED M0-1 "GAS-IN" M0-1 ) OUT = ( S1 
M0-1 ) \ \ BLOCK BLKID = FL1 BLKTYPE = "FLASH2" MDLTYPE = "Flash2" IN = ( S1 
M0-1 ) OUT = ( VAP M1-2 LIQ M2-3 ) \ \ BLOCK BLKID = HB BLKTYPE = "HIERARCHY" 
MDLTYPE = "Hierarchy" IN = ( LIQ M0-1 ) OUT = ( PROD M0-1 ) \ ? FLOWSHEET 
"HB.GLOBAL" ? \ BLOCK BLKID = P1 BLKTYPE = "PUMP" MDLTYPE = "Pump" IN = ( LIQ 
M0-1 ) OUT = ( PROD M0-1 ) \ ? STREAM MATERIAL FEED ? ; "METCBAR_MOLE" ; \ 
SUBSTREAM SSID = MIXED TEMP = 25. PRES = 1. \ ? BLOCK FLASH2 FL1 ? ; 
"METCBAR_MOLE" ; \ PARAM TEMP = 25. PRES = 0.1 \ ? BLOCK PUMP "HB.P1" ? \ PARAM 
PRES = 3. \ ? CALCULATOR "C-1" ? \ DEFINE FVN = FNACL FVN-VARTYPE = "MOLE-FLOW" 
\ \ FORTRAN FORTRAN-EXEC = ( "      FH2O = 55.5 * FNACL" ) \ ? "DESIGN-SPEC" 
"DS-1" ? \ DEFINE FVN = XCO2 FVN-VARTYPE = "MOLE-FRAC" \ ? TEAR ? \ TEAR SID = 
LIQ \ 
 GRAPHICS_BACKUP
PFS V 5.00
$_SUMMARY_FILE
 DSET RUN-STATUS VERS @VERS ( "41.0" "WIN-X64" "JDOE" "PC-123" "" )
 DSET RUN-STATUS IT @IT ( "OCTOBER 5, 2026  10:00:00 A.M." "_0001abc.inm" 4) 
"""

# Methanol-water column: no results stored, a sensitivity study and a user sequence.
BKP_COLUMN = _BKP_HEAD.format(date="Mon Oct  5 11:00:00 2026") + r"""2
>VERSION 0
COL
RadFrac
Built-In
RADFRAC
? SETUP MAIN ? \ "RUN-CLASS" RUN-CLASS = FLOWSHEET \ ? COMPONENTS MAIN ? \ 
COMPONENTS CID = METHANOL ANAME = CH4O OUTNAME = METHANOL DBNAME1 = "METHANOL" 
ANAME1 = "CH4O" /  CID = WATER ANAME = H2O OUTNAME = WATER DBNAME1 = "WATER" 
ANAME1 = "H2O" \ ? PROPERTIES MAIN ? \ GPROPERTIES GBASEOPSET = NRTL GOPSETNAME 
= NRTL \ ? FLOWSHEET GLOBAL ? \ BLOCK BLKID = COL BLKTYPE = "RADFRAC" MDLTYPE = 
"RadFrac" IN = ( FEED M0-1 ) OUT = ( DIST M1-2 BTMS M2-3 ) \ \ BLOCK BLKID = 
COND BLKTYPE = "HEATER" MDLTYPE = "Heater" IN = ( DIST M0-1 ) OUT = ( D2 M0-1 ) 
\ ? SENSITIVITY "S-1" ? \ DEFINE FVN = XD \ ? SEQUENCE "SEQ-1" ? \ SEQUENCE 
BLOCK-TYPE = BLOCK BLOCK-ID = COL \ 
 GRAPHICS_BACKUP
PFS V 5.00
"""


def minimal_pdf(text: str) -> bytes:
    """A valid one-page PDF with one line of text (enough for pypdf's text extraction)."""
    content = ("BT /F1 12 Tf 72 720 Td (" + text + ") Tj ET").encode("latin-1")
    objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
        b"/Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length " + str(len(content)).encode() + b" >>\nstream\n" + content + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = b"%PDF-1.4\n"
    offsets = []
    for i, o in enumerate(objs, 1):
        offsets.append(len(out))
        out += str(i).encode() + b" 0 obj\n" + o + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 " + str(len(objs) + 1).encode() + b"\n0000000000 65535 f \n"
    for off in offsets:
        out += ("%010d 00000 n \n" % off).encode()
    out += (b"trailer\n<< /Size " + str(len(objs) + 1).encode() + b" /Root 1 0 R >>\nstartxref\n"
            + str(xref).encode() + b"\n%%EOF\n")
    return out


def pdf_document(pages, title: str = "") -> bytes:
    """A valid PDF with one line of text per page and an optional /Title (enough for pypdf).
    Keep parentheses and backslashes out of the texts."""
    page_ids = [5 + 2 * k for k in range(len(pages))]
    objs = {
        1: b"<< /Type /Catalog /Pages 2 0 R >>",
        2: b"<< /Type /Pages /Kids [" + b" ".join(b"%d 0 R" % i for i in page_ids)
           + b"] /Count %d >>" % len(pages),
        3: b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        4: b"<< /Title (" + title.encode("latin-1") + b") >>",
    }
    for pid, text in zip(page_ids, pages):
        content = ("BT /F1 12 Tf 72 720 Td (" + text + ") Tj ET").encode("latin-1")
        objs[pid] = (b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents %d 0 R "
                     b"/Resources << /Font << /F1 3 0 R >> >> >>" % (pid + 1))
        objs[pid + 1] = b"<< /Length %d >>\nstream\n" % len(content) + content + b"\nendstream"
    out, offsets = b"%PDF-1.4\n", {}
    for i in sorted(objs):
        offsets[i] = len(out)
        out += b"%d 0 obj\n" % i + objs[i] + b"\nendobj\n"
    xref, size = len(out), max(objs) + 1
    out += b"xref\n0 %d\n0000000000 65535 f \n" % size
    for i in range(1, size):
        out += b"%010d 00000 n \n" % offsets[i]
    return out + b"trailer\n<< /Size %d /Root 1 0 R /Info 4 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (size, xref)


def make_example_library(root: Path) -> Path:
    """Three models in topic folders, like the Aspen Plus example library."""
    import zipfile
    a = root / "Carbon Capture" / "Brine absorber"
    write(a / "brine_absorber.bkp", BKP_DEMO)
    (a / "brine_absorber.pdf").write_bytes(minimal_pdf("Brine absorber guide: packing hydraulics and "
                                                       "rate-based mass transfer"))
    (a / "usrkin.f").write_text("      SUBROUTINE USRKIN\n      END\n", encoding="latin-1")
    write(root / "Getting Started" / "Distillation" / "methanol_column.bkp", BKP_COLUMN)
    p = root / "Getting Started" / "Packed" / "packed_column.apwz"
    p.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(str(p), "w") as z:
        z.writestr("packed_column.bkp", BKP_COLUMN.replace("11:00:00", "12:00:00").replace("\n", "\r\n"))
        z.writestr("usrpack.f", "      SUBROUTINE USRPACK\n      END\n")
    return root


# A complete input file: two feeds, mixer, heater, flash, calculator and sensitivity study.
INP_FLASH = """; methanol-water flash with a calculator and a sensitivity study
TITLE 'Methanol-water flash'
IN-UNITS MET PRESSURE=bar TEMPERATURE=C DELTA-T=C PDROP=bar
DEF-STREAMS CONVEN ALL
DATABANKS 'APV150 PURE41' / 'APV150 AQUEOUS' / 'APV150 SOLIDS' &
         / 'APV150 INORGANIC' / NOASPENPCD
PROP-SOURCES 'APV150 PURE41' / 'APV150 AQUEOUS' / 'APV150 SOLIDS' &
         / 'APV150 INORGANIC'
COMPONENTS
    METHANOL CH4O /
    WATER H2O
PROPERTIES NRTL
FLOWSHEET
    BLOCK MIX IN=FEED MAKEUP OUT=S1
    BLOCK HEAT IN=S1 OUT=S2
    BLOCK FL1 IN=S2 OUT=VAP LIQ
STREAM FEED
    SUBSTREAM MIXED TEMP=25. PRES=1.5 MOLE-FLOW=100.
    MOLE-FRAC METHANOL 0.4 / WATER 0.6
STREAM MAKEUP
    SUBSTREAM MIXED TEMP=25. PRES=1.5
    MOLE-FLOW WATER 10.
BLOCK MIX MIXER
    PARAM
BLOCK HEAT HEATER
    PARAM TEMP=80. PRES=0
BLOCK FL1 FLASH2
    PARAM TEMP=80. PRES=1.
CALCULATOR C-1
    DEFINE FMU MOLE-FLOW STREAM=MAKEUP SUBSTREAM=MIXED COMPONENT=WATER  &
        UOM="kmol/hr"
    DEFINE FTOT STREAM-VAR STREAM=FEED SUBSTREAM=MIXED VARIABLE=MOLE-FLOW  &
        UOM="kmol/hr"
F     FMU = 0.1 * FTOT
    READ-VARS FTOT
    WRITE-VARS FMU
SENSITIVITY S-1
    DEFINE XMV MOLE-FRAC STREAM=VAP SUBSTREAM=MIXED COMPONENT=METHANOL
    TABULATE 1 "XMV"
    VARY BLOCK-VAR BLOCK=FL1 VARIABLE=TEMP SENTENCE=PARAM UOM="C"
    RANGE OPT-LIST=RANGE LOWER="70" UPPER="95" INCR="5"
STREAM-REPOR MOLEFLOW MASSFLOW MOLEFRAC
"""

# The same kind of file with one planted mistake per check (line numbers matter: keep the order).
INP_BAD = """TITLE 'planted mistakes'
DATABANKS 'APV150 PURE41' / 'APV140 AQUEOUS'
COMPONENTS
    H2O H2O /
    CO2 CO2 /
    H3O+ H3O+ /
    HCO3- HCO3- /
    NACL NACL /
    NA+ NA+ /
    CL- CL-
HENRY-COMPS HC-1 CO2
CHEMISTRY C-1
    STOIC 1 CO2 -1. / H2O -2. / HCO3- 1. / H3O+ 2.
    DISS NACL NA+ 1. / CL- 1.
CHEMISTRY C-2
    STOIC 1 H2O -2. / H3O+ 1. / OH- 1.
PROPERTIES ELECNRTL CHEMISTRY=C-1 HENRY-COMPS=HC-1 TRUE-COMPS=NO
FLOWSHEET
    BLOCK B1 IN=FEED OUT=S1
    BLOCK B2 IN=S1 OUT=S2 S3
    BLOCK B3 IN=S1 OUT=S4
    BLOCK B4 IN=S4 OUT=S5
    BLOCK R1 IN=S5 OUT=S6
STREAM FEED
    SUBSTREAM MIXED TEMP=25. PRES=1. VFRAC=0.
    MOLE-FRAC H2O 0.9 / CO2 0.1
BLOCK B1 HEATER
    PARAM TEMP=50.
BLOCK B2 FLASH2
    PARAM TEMP=50. PRES=1. VFRAC=0.5
BLOCK B3 COMPR
    PARAM PRES=5.
BLOCK R1 RSTOIC
    PARAM TEMP=50. PRES=1.
    STOIC 1 MIXED CO2 -1. / H2O -1. / CH4 1.
DESIGN-SPEC DS-1
    DEFINE X MOLE-FRAC STREAM=S2 SUBSTREAM=MIXED COMPONENT=CO2
    SPEC "X" TO "0.01"
    VARY BLOCK-VAR BLOCK=B1 VARIABLE=TEMP SENTENCE=PARAM
    LIMITS "20" "80"
SENSITIVITY S-1
    DEFINE Y MOLE-FRAC STREAM=S2 SUBSTREAM=MIXED COMPONENT=CO2
    VARY BLOCK-VAR BLOCK=B1 VARIABLE=TEMP SENTENCE=PARAM
CALCULATOR C-1
    DEFINE A MOLE-FLOW STREAM=FEED SUBSTREAM=MIXED COMPONENT=H2O
F     A = 2.0 * A
    READ-VARS A Z
DISABLE
    BLOCK B9
"""

# Stream results copied from the Aspen Plus results grid (tab-separated), apparent basis.
STREAM_TABLE = "\n".join("\t".join(r) for r in [
    ["", "Units", "FEED", "GAS", "LIQ"],
    ["Description", "", "", "", ""],
    ["From", "", "", "FL1", "FL1"],
    ["To", "", "FL1", "", ""],
    ["Stream Class", "", "CONVEN", "CONVEN", "CONVEN"],
    ["Phase", "", "Liquid Phase", "Vapor Phase", "Liquid Phase"],
    ["Temperature", "C", "25", "25", "25"],
    ["Pressure", "bar", "1", "0.1", "0.1"],
    ["Mole Flows", "kmol/hr", "10.1", "0.06", "10.04"],
    ["H2O", "kmol/hr", "10", "0.04", "9.96"],
    ["CO2", "kmol/hr", "0.1", "0.02", "0.08"],
    ["NA+", "kmol/hr", "0", "0", "0"],
    ["HCO3-", "kmol/hr", "0", "0", "0"],
    ["Mass Flows", "kg/hr", "184.553", "1.6011", "182.952"],
    ["H2O", "kg/hr", "180.153", "0.72061", "179.432"],
    ["CO2", "kg/hr", "4.401", "0.88020", "3.5208"],
]) + "\n"


# ---------------------------------------------------------------------------
# v0.3: run stamps inside the files (freshness), several runs in one .his
# ---------------------------------------------------------------------------
def his_at(date: str, time: str, run_id: str = "_1234abc", text: str = HIS) -> str:
    """HIS with the file header and the run header stamped `date` ('OCTOBER 2, 2026') and `time`
    ('11:02:41 P.M.'), and another run ID."""
    return text.replace("MARCH 3, 2026", date).replace("10:15:02 A.M.", time).replace("_1234abc", run_id)


def rep_at(date: str, time: str, run_id: str = "_1234abc") -> str:
    """REP with the first-page header of a real report (date and time) and another run ID."""
    head = (" PLATFORM: WIN-X64                                       " + date + "\n"
            " VERSION: 41.0   Build 609                               TUESDAY\n"
            " INSTALLATION:                                           " + time + "\n\n")
    return head + REP.replace("_1234abc", run_id)


def bkp_at(when: str, run_id: str = "_1234abc", saved: str = "Mon Oct  5 10:00:00 2026") -> str:
    """BKP_DEMO holding the results of a run stamped `when` ('MARCH 4, 2026  09:00:30 A.M.')."""
    return (BKP_DEMO.replace('"OCTOBER 5, 2026  10:00:00 A.M." "_0001abc.inm"', f'"{when}" "{run_id}.inm"')
            .replace("Mon Oct  5 10:00:00 2026", saved))


def cpm_at(reinitialized: str, exported: str) -> str:
    """CPM whose two control-panel events carry other times ('10:15:00 Tue Mar 3, 2026')."""
    return (CPM.replace("Run reinitialized 10:15:00 Tue Mar 3, 2026", "Run reinitialized " + reinitialized)
            .replace("Report exported 10:15:05 Tue Mar 3, 2026", "Report exported " + exported))


# Two runs in one history: the original run (2 warnings), then an edit run a day later with a new
# split fraction and no warnings. Digests must describe the last run.
_SECOND_RUN = (HIS[HIS.index(" *** INPUT SUMMARY ***"):]
               .replace("ORIGINAL RUN                           MARCH 3, 2026",
                        "EDIT RUN                               MARCH 4, 2026")
               .replace("   10:15:02 A.M.                          TUESDAY",
                        "   09:00:00 A.M.                          WEDNESDAY")
               .replace("FRAC RECYCLE 0.3", "FRAC RECYCLE 0.4")
               .replace("        WARNINGS      1        0         1", "        WARNINGS      0        0         0"))
HIS_TWO_RUNS = HIS + "\n" + _SECOND_RUN


# ---------------------------------------------------------------------------
# v0.3.1: a synthetic case in place of the published example that left the repository.
# An invented isopropanol-to-acetone unit with a bottoms recycle ("SolvRec"): the backup was saved
# by V12.1 on 12 May 2026 with the results of a run of that day; the history, report and Control
# Panel files come from a V15 run on 21 Aug 2026. The report is lower-case like an Aspen export.
# Names, numbers and messages are made up; only the layouts follow Aspen Plus files.
# ---------------------------------------------------------------------------
SOLVREC_HIS = r""" + + + + + + + + + + + + + + + + + + + + + + + + + + + + + + + + + + + + + + + +
 + +                      ASPEN PLUS CALCULATION HISTORY                     + +
 + + + + + + + + + + + + + + + + + + + + + + + + + + + + + + + + + + + + + + + +

 PLATFORM: WIN-X64                                       AUGUST 21, 2026
 VERSION: 41.0   Build 609                               FRIDAY
 INSTALLATION:                                           02:30:41 P.M.

 THIS COPY OF ASPEN PLUS LICENSED TO NORTHWIND PROCESS LAB

 *** INPUT SUMMARY ***

 >>CURRENT RUN

   ORIGINAL RUN                           AUGUST 21, 2026
   02:30:41 P.M.                          FRIDAY
   INPUT FILE: _2207pqr.inm
   RUN ID : _2207pqr
          1    ;
          2    ;Input file created by Aspen Plus Rel. 41.0 at 14:30:39 Fri Aug 21, 2026
          3    ;Directory D:\Work\jsmith\SolvRec\v0.07  Runid SOLVREC
          4    ;
          5
          6    TITLE 'Solvent recovery demo'
          7
          8    IN-UNITS MET PRESSURE=bar TEMPERATURE=C DELTA-T=C PDROP=bar
          9
         10    DEF-STREAMS CONVEN ALL
         11
         12    DATABANKS 'APV150 PURE41' / 'APV150 AQUEOUS' / 'APV150 SOLIDS' &
         13             / 'APV150 INORGANIC' / NOASPENPCD
         14
         15    PROP-SOURCES 'APV150 PURE41' / 'APV150 AQUEOUS' / 'APV150 SOLIDS' &
         16             / 'APV150 INORGANIC'
         17
         18    COMPONENTS
         19        WATER H2O /
         20        ACETONE C3H6O-1 /
         21        IPA C3H8O-2 /
         22        H2 H2 /
         23        CO2 CO2 /
         24        N2 N2 /
         25        HEAVY /
         26        H3O+ H3O+ /
         27        OH- OH- /
         28        HCO3- HCO3-
         29
         30    HENRY-COMPS HC-1 H2 CO2 N2
         31
         32    CHEMISTRY C-W
         33        STOIC 1 WATER -2. / H3O+ 1. / OH- 1.
         34        K-STOIC 1 A=140.932 B=-13445.9 C=-22.4773
         35
         36    CHEMISTRY C-CO2
         37        STOIC 1 CO2 -1. / WATER -2. / HCO3- 1. / H3O+ 1.
         38        K-STOIC 1 A=231.465 B=-12092.1 C=-36.7816
         39
         40    FLOWSHEET
         41        BLOCK FEEDPUMP IN=FEED OUT=S1
         42        BLOCK PREHEAT IN=S1 OUT=S2
         43        BLOCK MIXREC IN=S2 RECYCLE OUT=S3
         44        BLOCK RX-STAGE IN=S3 OUT=S4
         45        BLOCK COL1 IN=S4 OUT=DIST BTMS
         46        BLOCK SPLIT1 IN=BTMS OUT=PURGE RECYCLE
         47        BLOCK GASCOMP IN=N2FEED OUT=GASHP
         48
         49    PROPERTIES NRTL HENRY-COMPS=HC-1
         50        PROPERTIES NRTL-HOC
         51
         52    PROP-DATA NRTL-1
         53        IN-UNITS SI
         54        PROP-LIST NRTL
         55        BPVAL WATER IPA 1.0120 315.27 .30 0.0 0.0 0.0 283.15  &
         56            373.15
         57        BPVAL IPA WATER -0.6631 105.81 .30 0.0 0.0 0.0 283.15  &
         58            373.15
         59
         60    PROP-DATA PLXANT-1
         61        IN-UNITS SI
         62        PROP-LIST PLXANT / MW
         63        PVAL HEAVY 58.71 -6912.4 0.0 0.0 -6.81 0.0 0.0 6.0 0.0  &
         64            0.0 290.0 470.0
         65        PVAL HEAVY 98.145
         66
         67    STREAM FEED
         68        SUBSTREAM MIXED TEMP=30. PRES=1.01325 MOLE-FLOW=100.
         69        MOLE-FRAC WATER 0.2 / IPA 0.8
         70
         71    STREAM N2FEED
         72        SUBSTREAM MIXED TEMP=25. PRES=1.01325 MOLE-FLOW=10.
         73        MOLE-FRAC N2 1.
         74
         75    STREAM RECYCLE
         76        SUBSTREAM MIXED TEMP=104. PRES=1.2 MOLE-FLOW=40.
         77        MOLE-FRAC WATER 0.65 / IPA 0.35
         78
         79    BLOCK MIXREC MIXER
         80        PARAM PRES=1.2
         81
         82    BLOCK SPLIT1 FSPLIT
         83        FRAC RECYCLE 0.6
         84        PROPERTIES NRTL HENRY-COMPS=HC-1
         85
         86    BLOCK PREHEAT HEATER
         87        PARAM TEMP=95. PRES=-0.2
         88
         89    BLOCK COL1 RADFRAC
         90        PARAM NSTAGE=18
         91        COL-CONFIG CONDENSER=PARTIAL-V
         92        FEEDS S4 9 ON-STAGE
         93        PRODUCTS DIST 1 V / BTMS 18 L
         94        P-SPEC 1 1.0
         95        COL-SPECS MOLE-RR=1.8 D:F=0.675
         96
         97    BLOCK RX-STAGE RSTOIC
         98        PARAM TEMP=150. PRES=1.1
         99        STOIC 1 MIXED IPA -1. / ACETONE 1. / H2 1.
        100        STOIC 2 MIXED ACETONE -2. / HEAVY 1. / WATER 1.
        101        CONV 1 MIXED IPA 0.75
        102        CONV 2 MIXED ACETONE 0.05
        103
        104    BLOCK FEEDPUMP PUMP
        105        PARAM PRES=6. EFF=0.6
        106
        107    BLOCK GASCOMP COMPR
        108        PARAM TYPE=ISENTROPIC PRES=8. SEFF=0.75
        109
        110    CALCULATOR RATIO
        111        DEFINE FIPA MOLE-FLOW STREAM=S2 SUBSTREAM=MIXED  &
        112            COMPONENT=IPA UOM="kmol/hr"
        113        DEFINE XEXT BLOCK-VAR BLOCK=RX-STAGE VARIABLE=CONV  &
        114            SENTENCE=CONV ID1=1
        115        DEFINE FSPARE MOLE-FLOW STREAM=S2 SUBSTREAM=MIXED  &
        116            COMPONENT=WATER UOM="kmol/hr"
        117    F     XEXT = 0.75D0 + 0.0D0 * FIPA
        118        READ-VARS FIPA FSPARE
        119        WRITE-VARS XEXT
        120
        121    DESIGN-SPEC DS-PUR
        122        DEFINE XACE MOLE-FRAC STREAM=DIST SUBSTREAM=MIXED  &
        123            COMPONENT=ACETONE
        124        SPEC "XACE" TO "0.5"
        125        TOL-SPEC "0.001"
        126        VARY BLOCK-VAR BLOCK=COL1 SENTENCE=COL-SPECS  &
        127            VARIABLE=MOLE-RR
        128        LIMITS "1." "4."
        129
        130    CONV-OPTIONS
        131        PARAM TEAR-METHOD=WEGSTEIN CHECKSEQ=NO
        132        WEGSTEIN MAXIT=100 QMIN=-5. QMAX=0.
        133
        134    REACTIONS R-COND REAC-DIST
        135        REAC-DATA 1 CONV
        136        STOIC 1 ACETONE -2. / HEAVY 1. / WATER 1.
        137        CONV 1 CONV-A=0.01 KEY-CID=ACETONE
        138
        139    STREAM-REPOR MOLEFLOW MOLEFRAC
        140
        141    DISABLE
        142        DESIGN-SPEC DS-PUR
        143
 *** INPUT TRANSLATOR MESSAGES ***

      INFORMATION                                              (PSTOP1AP.1)
      THERE ARE HENRY COMPONENTS DEFINED IN THIS CASE, THE BINARY DATABANK
      WILL BE SEARCHED AUTOMATICALLY FOR ANY AVAILABLE HENRY CONSTANTS.

 *** FLOWSHEET ANALYSIS MESSAGES ***

  *   WARNING WHILE CHECKING INPUT SPECIFICATIONS              (PRPCHK.1)
      INCONSISTENT PROPERTIES DETECTED FOR 1 STREAMS
      SOURCE BLOCK        PROPERTIES STREAM   DESTINATION BLOCK   PROPERTIES
      =================== ========== ======== =================== ==========
      SPLIT1              NRTL       RECYCLE  MIXREC              NRTL-HOC

      BLOCK $OLVER01 (METHOD: WEGSTEIN) HAS BEEN DEFINED TO CONVERGE
               STREAMS: RECYCLE

      COMPUTATION ORDER FOR THE FLOWSHEET IS:
      FEEDPUMP PREHEAT GASCOMP $OLVER01 MIXREC RX-STAGE RATIO COL1 SPLIT1
      (RETURN $OLVER01)

Calculations begin                                                              time      0.21


 SIMULATION CALCULATIONS BEGIN                                                    TIME =      0.21

      UOS BLOCK FEEDPUMP MODEL: PUMP                                              TIME =      0.21
      VOL-FLOW   =  0.1794E-02 , DELTA P    =  0.4987E+06 , PUMP EFF   =  0.6000
      FLUID PWR  =   894.86    , BRAKE PWR  =   1491.4    , ELEC PWR   =   1491.4

      UOS BLOCK PREHEAT  MODEL: HEATER                                            TIME =      0.22
      KODE = 2  NTRIAL =   1  T = 368.1500  P =  580000.      V =  0.00000      Q =  412345.

      UOS BLOCK GASCOMP  MODEL: COMPR                                             TIME =      0.22
      OUTLET TEMP =   617.9       OUTLET PRES =  0.8000E+06   INDICATED HP =  0.2594E+05   BRAKE HP =  0.2594E+05
      ISENTR TEMP =   538.0      CALC ISENTR EFF =  0.7500      ISENTR HP =  0.1946E+05  HP =  0.3479E+02

      CONVERGENCE BLOCK $OLVER01  METHOD: WEGSTEIN                                TIME =      0.22
      ITER   0 For Tear Streams: RECYCLE

      UOS BLOCK MIXREC   MODEL: MIXER                                             TIME =      0.22
      KODE = 1  NTRIAL =   6  T = 363.0021  P =  120000.      V = 0.312000      Q =  0.00000

      UOS BLOCK RX-STAGE MODEL: RSTOIC                                            TIME =      0.23

  *   WARNING WHILE EXECUTING UNIT OPERATIONS BLOCK: "RX-STAGE" (MODEL:
      "RSTOIC")                                                (URE07.2)
      REACTION NO. "2" IS DROPPED BECAUSE REACTANT "ACETONE" HAS ZERO INLET
      FLOW RATE.
      KODE = 2  NTRIAL =   3  T = 423.1500  P =  110000.      V =  1.00000      Q =  298712.

      CALCULATOR BLOCK RATIO                                                      TIME =      0.23

      UOS BLOCK COL1     MODEL: RADFRAC                                           TIME =      0.24

       Convergence iterations:
         OL   ML   IL     Err/Tol
          1    1    5      412.07
          2    4   11      17.235
          3    3    6     0.41023

      UOS BLOCK SPLIT1   MODEL: FSPLIT                                            TIME =      0.25

      CONVERGENCE BLOCK $OLVER01  METHOD: WEGSTEIN                                TIME =      0.25
      ITER   1 For Tear Streams: RECYCLE

  LOOP $OLVER01 ITER    1:   4 VARS NOT CONVERGED, MAX ERR/TOL      210.40        TIME =      0.25

      UOS BLOCK MIXREC   MODEL: MIXER                                             TIME =      0.26
      KODE = 1  NTRIAL =   5  T = 361.8805  P =  120000.      V = 0.041200      Q =  0.00000

      UOS BLOCK RX-STAGE MODEL: RSTOIC                                            TIME =      0.26
      KODE = 2  NTRIAL =   3  T = 423.1500  P =  110000.      V =  1.00000      Q =  301845.

      CALCULATOR BLOCK RATIO                                                      TIME =      0.26

      UOS BLOCK COL1     MODEL: RADFRAC                                           TIME =      0.27

       Convergence iterations:
         OL   ML   IL     Err/Tol
          1    1    4      38.112
          2    2    5     0.52007

      UOS BLOCK SPLIT1   MODEL: FSPLIT                                            TIME =      0.28

      CONVERGENCE BLOCK $OLVER01  METHOD: WEGSTEIN                                TIME =      0.28
      ITER   2 For Tear Streams: RECYCLE

  LOOP $OLVER01 ITER    2:     *** CONVERGED *** , MAX ERR/TOL      0.3120        TIME =      0.28

      GENERATING RESULTS FOR UOS BLOCK FEEDPUMP MODEL: PUMP                       TIME =      0.31
      KODE = 5  NTRIAL =   2  T = 303.5626  P =  100261.      V =  0.00000      Q =  0.00000
      VOL-FLOW   =  0.1794E-02 , DELTA P    =  0.4987E+06 , PUMP EFF   =  0.6000
      FLUID PWR  =   894.86    , BRAKE PWR  =   1491.4    , ELEC PWR   =   1491.4
      NPSH AVAIL =  0.1258E+02

      GENERATING RESULTS FOR UOS BLOCK PREHEAT  MODEL: HEATER                     TIME =      0.31

 Report Writer entered                                                            Time =      0.32

 Results generated                                                                Time =      0.36

RUN SAVED



 *** SUMMARY OF ERRORS ***

                  PHYSICAL
                  PROPERTY  SYSTEM  SIMULATION
 TERMINAL ERRORS      0        0         0
   SEVERE ERRORS      0        0         0
          ERRORS      0        0         0
        WARNINGS      0        1         1
"""

SOLVREC_REP = r"""

 + + + + + + + + + + + + + + + + + + + + + + + + + + + + + + + + + + + + + + + +
 + +                                                                         + +
 + +                      ASPEN PLUS CALCULATION REPORT                      + +
 + +                                                                         + +
 + + + + + + + + + + + + + + + + + + + + + + + + + + + + + + + + + + + + + + + +

 PLATFORM: WIN-X64                                       AUGUST 21, 2026
 VERSION: 41.0   Build 609                               FRIDAY
 INSTALLATION:                                           02:30:52 P.M.

 ASPEN PLUS   PLAT: WIN-X64   VER: 41.0                   08/21/2026  PAGE    I

                               TABLE OF CONTENTS

            RUN CONTROL SECTION....................................  1
                 RUN CONTROL INFORMATION...........................  1

            FLOWSHEET SECTION......................................  2
                 FLOWSHEET CONNECTIVITY BY STREAMS.................  2
                 OVERALL FLOWSHEET BALANCE.........................  2

            U-O-S BLOCK SECTION....................................  3
                 BLOCK:  FEEDPUMP MODEL: PUMP......................  3
                 BLOCK:  COL1     MODEL: RADFRAC...................  4

            STREAM SECTION.........................................  6

            PROBLEM STATUS SECTION.................................  9

@FF@ ASPEN PLUS   PLAT: WIN-X64   VER: 41.0                   08/21/2026  PAGE 1  

                              RUN CONTROL SECTION

 RUN CONTROL INFORMATION
 -----------------------

 THIS COPY OF ASPEN PLUS LICENSED TO NORTHWIND PROCESS LAB

 TYPE OF RUN: NEW

 INPUT FILE NAME: _2207pqr.inm

 OUTPUT PROBLEM DATA FILE NAME: _2207pqr
 LOCATED IN: D:\Work\jsmith\SolvRec\v0.07

 CALLING PROGRAM NAME:          apmain
 LOCATED IN: C:\Program Files\AspenTech\Aspen Plus V15.0\Engine\xeq

 SIMULATION REQUESTED FOR ENTIRE FLOWSHEET
@FF@ ASPEN PLUS   PLAT: WIN-X64   VER: 41.0                   08/21/2026  PAGE 2  

                               FLOWSHEET SECTION

 FLOWSHEET CONNECTIVITY BY STREAMS
 ---------------------------------

   STREAM     SOURCE     DEST           STREAM     SOURCE     DEST
   FEED       ----       FEEDPUMP       N2FEED     ----       GASCOMP
   S1         FEEDPUMP   PREHEAT        S2         PREHEAT    MIXREC
   S3         MIXREC     RX-STAGE       S4         RX-STAGE   COL1
   DIST       COL1       ----           BTMS       COL1       SPLIT1
   PURGE      SPLIT1     ----           RECYCLE    SPLIT1     MIXREC
   GASHP      GASCOMP    ----

 FLOWSHEET CONNECTIVITY BY BLOCKS
 --------------------------------

   BLOCK        INLETS                         OUTLETS
   FEEDPUMP     FEED                           S1
   PREHEAT      S1                             S2
   MIXREC       S2 RECYCLE                     S3
   RX-STAGE     S3                             S4
   COL1         S4                             DIST BTMS
   SPLIT1       BTMS                           PURGE RECYCLE
   GASCOMP      N2FEED                         GASHP

 CONVERGENCE STATUS SUMMARY
 --------------------------

   TEAR STREAM SUMMARY
   ===================

   STREAM    VARIABLE         MAXIMUM      MAX. ERR.    ABSOLUTE          CONV
   ID        ID               ERR/TOL      RELATIVE     ERROR       STAT  BLOCK
   ------    --------         --------     -------      ---------   ----  -----
   RECYCLE  WATER MOLEFLOW     0.3120       0.3120E-04   0.2297E-06  #    $OLVER01

   #  = CONVERGED
   *  = NOT CONVERGED

 OVERALL FLOWSHEET BALANCE
 -------------------------

                      ***  MASS AND ENERGY BALANCE  ***
                              IN          OUT       GENERATION   RELATIVE DIFF.
    TOTAL BALANCE
       MOLE(KMOL/HR )         110.000       180.340       70.3400      -0.157E-15
       MASS(KG/HR   )         5448.11       5448.11                     0.214E-09
       ENTHALPY(CAL/SEC )    -0.186640E+07 -0.152217E+07               -0.184435
@FF@ ASPEN PLUS   PLAT: WIN-X64   VER: 41.0                   08/21/2026  PAGE 3  

                              U-O-S BLOCK SECTION

 BLOCK:  FEEDPUMP MODEL: PUMP
 ----------------------------
   INLET STREAM:          FEED
   OUTLET STREAM:         S1
   PROPERTY OPTION SET:   NRTL      RENON (NRTL) / IDEAL GAS

                      ***  MASS AND ENERGY BALANCE  ***
                                    IN              OUT        RELATIVE DIFF.
    TOTAL BALANCE
       MOLE(KMOL/HR )            100.000         100.000         0.00000
       MASS(KG/HR   )            5167.98         5167.98         0.00000
       ENTHALPY(CAL/SEC )      -0.186667E+07   -0.186631E+07   -0.190727E-03

                          ***  INPUT DATA  ***
   OUTLET PRESSURE BAR                                           6.00000
   PUMP EFFICIENCY                                               0.60000
   DRIVER EFFICIENCY                                             1.00000

                           ***  RESULTS  ***
   VOLUMETRIC FLOW RATE L/MIN                                  107.667
   PRESSURE CHANGE BAR                                           4.98675
   NPSH AVAILABLE   M-KGF/KG                                    12.5780
   FLUID POWER KW                                                0.89486
   BRAKE POWER KW                                                1.49143
   ELECTRICITY KW                                                1.49143
   PUMP EFFICIENCY USED                                          0.60000
   NET WORK REQUIRED KW                                          1.49143
   HEAD DEVELOPED M-KGF/KG                                      63.5391

 BLOCK:  GASCOMP  MODEL: COMPR
 -----------------------------
   INLET STREAM:          N2FEED
   OUTLET STREAM:         GASHP
   PROPERTY OPTION SET:   NRTL      RENON (NRTL) / IDEAL GAS

                           ***  RESULTS  ***

   INDICATED  HORSEPOWER REQUIREMENT   KW                       25.9412
   BRAKE      HORSEPOWER REQUIREMENT   KW                       25.9412
   NET WORK REQUIRED                   KW                       25.9412
   ISENTROPIC HORSEPOWER REQUIREMENT   KW                       19.4559
   CALCULATED OUTLET TEMP  C                                   344.751
   ISENTROPIC TEMPERATURE C                                    264.851
   EFFICIENCY (POLYTR/ISENTR) USED                               0.75000
   OUTLET VAPOR FRACTION                                         1.00000
   MECHANICAL EFFICIENCY USED                                    1.00000

 BLOCK:  RX-STAGE MODEL: RSTOIC
 ------------------------------
   INLET STREAM:          S3
   OUTLET STREAM:         S4
   PROPERTY OPTION SET:   NRTL      RENON (NRTL) / IDEAL GAS

                           ***  RESULTS  ***
   OUTLET TEMPERATURE    C                                     150.00
   OUTLET PRESSURE       BAR                                     1.1000
   HEAT DUTY             CAL/SEC                            301,845.
   VAPOR FRACTION                                                1.0000

   REACTION EXTENTS:

     REACTION          REACTION
     NUMBER            EXTENT
                       KMOL/HR
     1                  70.340
     2                  0.02135

 BLOCK:  COL1     MODEL: RADFRAC
 -------------------------------
    INLETS   - S4       STAGE   9
    OUTLETS  - DIST     STAGE   1
               BTMS     STAGE  18
@FF@ ASPEN PLUS   PLAT: WIN-X64   VER: 41.0                   08/21/2026  PAGE 4  

                              U-O-S BLOCK SECTION

 BLOCK:  COL1     MODEL: RADFRAC (CONTINUED)
   PROPERTY OPTION SET:   NRTL      RENON (NRTL) / IDEAL GAS
   HENRY-COMPS ID:        HC-1

                      ***  MASS AND ENERGY BALANCE  ***
                                    IN              OUT        RELATIVE DIFF.
    TOTAL BALANCE
       MOLE(KMOL/HR )            211.552         211.552        -0.14E-15
       MASS(KG/HR   )            6527.35         6527.35         0.11E-12
       ENTHALPY(CAL/SEC )      -0.201190E+07   -0.236514E+07    0.149353

                          **********************
                          ****  INPUT DATA  ****
                          **********************

   ****   INPUT PARAMETERS   ****

    NUMBER OF STAGES                                           18
    ALGORITHM OPTION                                         STANDARD
    INITIALIZATION OPTION                                    STANDARD
    MAXIMUM NO. OF OUTSIDE LOOP ITERATIONS                     25
    OUTSIDE LOOP CONVERGENCE TOLERANCE                          0.000100000

   ****   COL-SPECS   ****

    MOLAR VAPOR DIST / TOTAL DIST                               1.00000
    MOLAR REFLUX RATIO                                          1.80000
    DISTILLATE TO FEED RATIO                                    0.67500

   ****    PROFILES   ****

    P-SPEC          STAGE   1  PRES, BAR                        1.00000

@FF@ ASPEN PLUS   PLAT: WIN-X64   VER: 41.0                   08/21/2026  PAGE 5  

                              U-O-S BLOCK SECTION

 BLOCK:  COL1     MODEL: RADFRAC (CONTINUED)

                          *******************
                          ****  RESULTS  ****
                          *******************


   ***   COMPONENT SPLIT FRACTIONS   ***

                             OUTLET STREAMS
                             --------------
                  DIST         BTMS
    COMPONENT:
    WATER       .50000E-01   .95000
    ACETONE     .98000       .20000E-01
    IPA         .20000E-01   .98000
    H2          1.0000       0.0000
    CO2         MISSING      MISSING
    HEAVY       0.0000       1.0000

 
   ***    SUMMARY OF KEY RESULTS    ***

    TOP STAGE TEMPERATURE          C                        38.2417
    BOTTOM STAGE TEMPERATURE       C                       104.602
    TOP STAGE LIQUID FLOW          KMOL/HR                 262.930
    BOTTOM STAGE LIQUID FLOW       KMOL/HR                  68.6873
    TOP STAGE VAPOR FLOW           KMOL/HR                 142.865
    BOILUP VAPOR FLOW              KMOL/HR                 187.402
    MOLAR REFLUX RATIO                                       1.80000
    MOLAR BOILUP RATIO                                       2.79410
    CONDENSER DUTY (W/O SUBCOOL)   CAL/SEC                  -0.121733+07
    REBOILER DUTY                  CAL/SEC           1,482,650.

   ****   MAXIMUM FINAL RELATIVE ERRORS   ****

    DEW POINT                       0.31277E-04  STAGE=  4
    BUBBLE POINT                    0.20846E-04  STAGE= 17
    COMPONENT MASS BALANCE          0.61902E-15  STAGE=  9 COMP=IPA
    ENERGY BALANCE                  0.47105E-04  STAGE= 16

   ****    PROFILES   ****

                                   ENTHALPY
  STAGE TEMPERATURE   PRESSURE         CAL/MOL             HEAT DUTY
          C            BAR         LIQUID       VAPOR        CAL/SEC

    1   38.242        1.0000      -61502.      -24210.     -.12173+07
    2   57.913        1.0118      -62230.      -47785.
    9   81.264        1.0941      -65117.      -51938.
   17   99.870        1.1882      -67350.      -55240.
   18   104.60        1.2000      -67812.      -56021.      .14827+07

  STAGE      FLOW RATE               FEED RATE               PRODUCT RATE
              KMOL/HR                 KMOL/HR                   KMOL/HR
       LIQUID    VAPOR         LIQUID   VAPOR    MIXED      LIQUID    VAPOR
    1  262.9     142.9                                              142.8651
    9  271.5     409.0                 211.5524
   18  68.69     187.4                                    68.6873

@FF@ ASPEN PLUS   PLAT: WIN-X64   VER: 41.0                   08/21/2026  PAGE 6  

                                 STREAM SECTION

 BTMS DIST FEED GASHP N2FEED                
 -----------------------------

 STREAM ID               BTMS       DIST       FEED       GASHP      N2FEED     
 FROM :                  COL1       COL1       ----       GASCOMP    ----     
 TO   :                  SPLIT1     ----       FEEDPUMP   ----       GASCOMP     

 SUBSTREAM: MIXED   
 PHASE:                  LIQUID     MIXED      LIQUID     VAPOR      VAPOR     
 COMPONENTS: KMOL/HR         
   WATER                 44.2332     2.3281    20.0000     0.0        0.0   
   ACETONE                1.4230    69.7281     0.0        0.0        0.0   
   IPA                   22.9777     0.4689    80.0000     0.0        0.0   
   H2                     0.0       70.3400     0.0        0.0        0.0   
   CO2                    0.0        0.0        0.0        0.0        0.0   
   N2                     0.0        0.0        0.0       10.0000    10.0000
   HEAVY               5.3363-02     0.0        0.0        0.0        0.0   
   H3O+                   0.0        0.0        0.0        0.0        0.0   
   OH-                    0.0        0.0        0.0        0.0        0.0   
   HCO3-                  0.0        0.0        0.0        0.0        0.0   
 COMPONENTS: MOLE FRAC       
   WATER                  0.6440  1.6296-02     0.2000     0.0        0.0   
   ACETONE             2.0717-02     0.4881     0.0        0.0        0.0   
   IPA                    0.3345  3.2824-03     0.8000     0.0        0.0   
   H2                     0.0        0.4924     0.0        0.0        0.0   
@FF@ ASPEN PLUS   PLAT: WIN-X64   VER: 41.0                   08/21/2026  PAGE 7  

                                 STREAM SECTION

 BTMS DIST FEED GASHP N2FEED (CONTINUED)        

 STREAM ID               BTMS       DIST       FEED       GASHP      N2FEED     

   CO2                    0.0        0.0        0.0        0.0        0.0   
   N2                     0.0        0.0        0.0        1.0000     1.0000
   HEAVY               7.7690-04     0.0        0.0        0.0        0.0   
   H3O+                   0.0        0.0        0.0        0.0        0.0   
   OH-                    0.0        0.0        0.0        0.0        0.0   
   HCO3-                  0.0        0.0        0.0        0.0        0.0   
 TOTAL FLOW:         
   KMOL/HR               68.6873   142.8651   100.0000    10.0000    10.0000
   KG/HR               2265.6170  4261.7332  5167.9800   280.1300   280.1300
   L/MIN                 47.7978  3551.4443   109.0291  1070.2564  4077.3404
 STATE VARIABLES:    
   TEMP   C             104.6021    38.2417    30.0000   344.7512    25.0000
   PRES   BAR             1.2000     1.0000     1.0132     8.0000     1.0132
   VFRAC                  0.0        0.5263     0.0        1.0000     1.0000
   LFRAC                  1.0000     0.4737     1.0000     0.0        0.0   
   SFRAC                  0.0        0.0        0.0        0.0        0.0   
 ENTHALPY:           
   CAL/MOL            -6.7200+04 -5.2100+04 -6.7200+04  2271.5000    -1.2507
   CAL/GM             -2037.3203 -1746.5357 -1300.3146    81.0874 -4.4647-02
   CAL/SEC            -1.2822+06 -2.0676+06 -1.8667+06  6309.7222    -3.4742
 AVG MW                  32.9845    29.8305    51.6798    28.0130    28.0130

 PURGE RECYCLE S1 S2 S3                
 ------------------------

 STREAM ID               PURGE      RECYCLE    S1         S2         S3     
 FROM :                  SPLIT1     SPLIT1     FEEDPUMP   PREHEAT    MIXREC     
 TO   :                  ----       MIXREC     PREHEAT    MIXREC     RX-STAGE     

 SUBSTREAM: MIXED   
 PHASE:                  LIQUID     LIQUID     LIQUID     LIQUID     MIXED     
 COMPONENTS: KMOL/HR         
   WATER                 17.6933    26.5399    20.0000    20.0000    46.5399
   ACETONE                0.5692     0.8538     0.0        0.0        0.8538
   IPA                    9.1911    13.7866    80.0000    80.0000    93.7866
   H2                     0.0        0.0        0.0        0.0        0.0   
   CO2                    0.0        0.0        0.0        0.0        0.0   
   N2                     0.0        0.0        0.0        0.0        0.0   
   HEAVY               2.1345-02  3.2018-02     0.0        0.0     3.2018-02
   H3O+                   0.0        0.0        0.0        0.0        0.0   
   OH-                    0.0        0.0        0.0        0.0        0.0   
   HCO3-                  0.0        0.0        0.0        0.0        0.0   
 COMPONENTS: MOLE FRAC       
   WATER                  0.6440     0.6440     0.2000     0.2000     0.3296
   ACETONE             2.0717-02  2.0717-02     0.0        0.0     6.0463-03
   IPA                    0.3345     0.3345     0.8000     0.8000     0.6642
   H2                     0.0        0.0        0.0        0.0        0.0   
@FF@ ASPEN PLUS   PLAT: WIN-X64   VER: 41.0                   08/21/2026  PAGE 8  

                                 STREAM SECTION

 PURGE RECYCLE S1 S2 S3 (CONTINUED)        

 STREAM ID               PURGE      RECYCLE    S1         S2         S3     

   CO2                    0.0        0.0        0.0        0.0        0.0   
   N2                     0.0        0.0        0.0        0.0        0.0   
   HEAVY               7.7690-04  7.7690-04     0.0        0.0     2.2674-04
   H3O+                   0.0        0.0        0.0        0.0        0.0   
   OH-                    0.0        0.0        0.0        0.0        0.0   
   HCO3-                  0.0        0.0        0.0        0.0        0.0   
 TOTAL FLOW:         
   KMOL/HR               27.4749    41.2124   100.0000   100.0000   141.2124
   KG/HR                906.2468  1359.3702  5167.9800  5167.9800  6527.3502
   L/MIN                 19.1191    28.6787   109.0291   109.0291  5439.4585
 STATE VARIABLES:    
   TEMP   C             104.6021   104.6021    30.4126    95.0000    88.7305
   PRES   BAR             1.2000     1.2000     6.0000     5.8000     1.2000
   VFRAC                  0.0        0.0        0.0        0.0     4.1200-02
   LFRAC                  1.0000     1.0000     1.0000     1.0000     0.9588
   SFRAC                  0.0        0.0        0.0        0.0        0.0   
 ENTHALPY:           
   CAL/MOL            -6.7200+04 -6.7200+04 -6.7200+04 -6.7200+04 -5.2100+04
   CAL/GM             -2037.3203 -2037.3203 -1300.3146 -1300.3146 -1127.1290
   CAL/SEC            -5.1287+05 -7.6930+05 -1.8667+06 -1.8667+06 -2.0437+06
 AVG MW                  32.9845    32.9845    51.6798    51.6798    46.2236

 S4                
 ----

 STREAM ID               S4     
 FROM :                  RX-STAGE     
 TO   :                  COL1     

 SUBSTREAM: MIXED   
 PHASE:                  VAPOR     
 COMPONENTS: KMOL/HR         
   WATER                 46.5613
   ACETONE               71.1511
   IPA                   23.4467
   H2                    70.3400
   CO2                    0.0   
   N2                     0.0   
   HEAVY               5.3363-02
   H3O+                   0.0   
   OH-                    0.0   
   HCO3-                  0.0   
 COMPONENTS: MOLE FRAC       
   WATER                  0.2201
   ACETONE                0.3363
   IPA                    0.1108
   H2                     0.3325
   CO2                    0.0   
   N2                     0.0   
   HEAVY               2.5225-04
   H3O+                   0.0   
   OH-                    0.0   
   HCO3-                  0.0   
 TOTAL FLOW:         
   KMOL/HR              211.5524
   KG/HR               6527.3502
   L/MIN               1.1277+05
 STATE VARIABLES:    
   TEMP   C             150.0000
   PRES   BAR             1.1000
   VFRAC                  1.0000
   LFRAC                  0.0   
   SFRAC                  0.0   
 ENTHALPY:           
   CAL/MOL            -4100.0000
   CAL/GM              -132.8816
   CAL/SEC            -2.4093+05
 AVG MW                  30.8545
@FF@ ASPEN PLUS   PLAT: WIN-X64   VER: 41.0                   08/21/2026  PAGE 9  

                             PROBLEM STATUS SECTION

 BLOCK STATUS
 ------------

 ****************************************************************************
 *                                                                          *
 * Calculations were completed normally                                     *
 *                                                                          *
 * All Unit Operation blocks were completed normally                        *
 *                                                                          *
 * All streams were flashed normally                                        *
 *                                                                          *
 * All Convergence blocks were completed normally                           *
 *                                                                          *
 ****************************************************************************
""".replace("@FF@", "\f")

SOLVREC_CPM = """<< Run reinitialized 14:30:38 Fri Aug 21, 2026>>

->Processing input specifications ...

      INFORMATION
      THERE ARE HENRY COMPONENTS DEFINED IN THIS CASE, THE BINARY DATABANK
      WILL BE SEARCHED AUTOMATICALLY FOR ANY AVAILABLE HENRY CONSTANTS.

  Flowsheet Analysis :

 Block $OLVER01 (Method: WEGSTEIN) has been defined to converge
         streams: RECYCLE

 COMPUTATION ORDER FOR THE FLOWSHEET:
 FEEDPUMP PREHEAT GASCOMP $OLVER01 MIXREC RX-STAGE RATIO COL1 SPLIT1
 (RETURN $OLVER01)

->Calculations begin ...

   Block: FEEDPUMP Model: PUMP

   Block: PREHEAT  Model: HEATER

   Block: GASCOMP  Model: COMPR

> Beginning Convergence Loop $OLVER01 Method: WEGSTEIN
  Converging tear streams: RECYCLE

   Block: MIXREC   Model: MIXER

   Block: RX-STAGE Model: RSTOIC
  *   WARNING
      REACTION NO. "2" IS DROPPED BECAUSE REACTANT "ACETONE" HAS ZERO INLET
      FLOW RATE.

   Calculator Block RATIO

   Block: COL1     Model: RADFRAC

       Convergence iterations:
         OL   ML   IL     Err/Tol
          1    1    5      412.07
          2    4   11      17.235
          3    3    6     0.41023

   Block: SPLIT1   Model: FSPLIT

> Loop $OLVER01 Method: WEGSTEIN     Iteration    1
  Converging tear streams: RECYCLE
   4 vars not converged, Max Err/Tol   0.21040E+03

   Block: MIXREC   Model: MIXER

   Block: RX-STAGE Model: RSTOIC

   Calculator Block RATIO

   Block: COL1     Model: RADFRAC

       Convergence iterations:
         OL   ML   IL     Err/Tol
          1    1    4      38.112
          2    2    5     0.52007

   Block: SPLIT1   Model: FSPLIT

> Loop $OLVER01 Method: WEGSTEIN     Iteration    2
  Converging tear streams: RECYCLE
# Converged              Max Err/Tol   0.31200E+00

->Simulation calculations completed ...

               ***  Summary of Simulation Errors  ***

                   Physical
                   Property         System        Simulation
  Terminal Errors      0               0               0
    Severe Errors      0               0               0
           Errors      0               0               0
         Warnings      0               1               1

->Checking phase equilibrium results ...

->Generating results ...


  ***  Warning(s) were issued during Input Translation ***
  ***  Check the Run Status Results for more Information ***


<< Report exported 14:31:20 Fri Aug 21, 2026>>
"""

SOLVREC_BKP = r"""MM "39.0" FLAVOR "NO" VERSION "39.0" DATETIME "Tue May 12 09:41:10 2026"
MACHINE "WIN-NT/VC"  ;
startlibrary
version1
NumLibs = 1
Built-In
NumCats = 1
Separators
active
endlibrary
;
7
>VERSION 0
FEEDPUMP
Pump
Built-In
PUMP
>VERSION 0
PREHEAT
Heater
Built-In
HEATER
>VERSION 0
MIXREC
Mixer
Built-In
MIXER
>VERSION 0
RX-STAGE
RStoic
Built-In
RSTOIC
>VERSION 0
COL1
RadFrac
Built-In
RADFRAC
>VERSION 0
SPLIT1
FSplit
Built-In
FSPLIT
>VERSION 0
GASCOMP
Compr
Built-In
COMPR
? SETUP MAIN ? \ "RUN-CLASS" RUN-CLASS = FLOWSHEET \ \ SIMULATE INTERACTIVE = 
NO \ ? SETUP DESCRIPTION ? \ DESCRIPTION DESCRIP = ( "Solvent recovery demo: 
isopropanol to acetone" "with a bottoms recycle" ) \ ? SETUP "UNITS-SET" "US-1" 
? \ DESCRIPTION DESCRIPTION = "Units of the demo" \ \ UNITSET BASESET = MET ( 3 
3 3 13 3 ) \ ? COMPONENTS MAIN ? \ COMPONENTS CID = WATER ANAME = H2O OUTNAME = 
WATER DBNAME1 = "WATER" ANAME1 = "H2O" / CID = ACETONE ANAME = "C3H6O-1" 
OUTNAME = ACETONE DBNAME1 = "ACETONE" ANAME1 = "C3H6O-1" / CID = IPA ANAME = 
"C3H8O-2" OUTNAME = IPA DBNAME1 = "ISOPROPYL-ALCOHOL" ANAME1 = "C3H8O-2" / CID 
= H2 ANAME = H2 OUTNAME = H2 DBNAME1 = "HYDROGEN" ANAME1 = "H2" / CID = CO2 
ANAME = CO2 OUTNAME = CO2 DBNAME1 = "CARBON-DIOXIDE" ANAME1 = "CO2" / CID = N2 
ANAME = N2 OUTNAME = N2 DBNAME1 = "NITROGEN" ANAME1 = "N2" / CID = HEAVY 
OUTNAME = HEAVY / CID = "H3O+" ANAME = "H3O+" OUTNAME = "H3O+" DBNAME1 = "H3O+" 
ANAME1 = "H3O+" / CID = "OH-" ANAME = "OH-" OUTNAME = "OH-" DBNAME1 = "OH-" 
ANAME1 = "OH-" / CID = "HCO3-" ANAME = "HCO3-" OUTNAME = "HCO3-" DBNAME1 = 
"HCO3-" ANAME1 = "HCO3-" \ ? COMPONENTS "HENRY-COMPS" "HC-1" ? \ "HENRY-COMPS" 
CID = ( H2 CO2 N2 ) \ ? CHEMISTRY "C-W" ? \ STOIC REACNO = 1 STOIC-CID = WATER 
COEF = -2. <0> <0> / REACNO = 1 STOIC-CID = "H3O+" COEF = 1. <0> <0> / REACNO = 
1 STOIC-CID = "OH-" COEF = 1. <0> <0> \ ? CHEMISTRY "C-CO2" ? \ STOIC REACNO = 
1 STOIC-CID = CO2 COEF = -1. <0> <0> / REACNO = 1 STOIC-CID = WATER COEF = -2. 
<0> <0> / REACNO = 1 STOIC-CID = "HCO3-" COEF = 1. <0> <0> / REACNO = 1 
STOIC-CID = "H3O+" COEF = 1. <0> <0> \ ? PROPERTIES MAIN ? \ GPROPERTIES 
GPPROCTYPE = ALL GBASEOPSET = NRTL GOPSETNAME = NRTL GHEN = "HC-1" \ ? 
FLOWSHEET GLOBAL ? \ BLOCK BLKID = FEEDPUMP BLKTYPE = "PUMP" MDLTYPE = "Pump" 
IN = ( FEED M0-1 ) OUT = ( S1 M0-1 ) \ \ BLOCK BLKID = PREHEAT BLKTYPE = 
"HEATER" MDLTYPE = "Heater" IN = ( S1 M0-1 ) OUT = ( S2 M0-1 ) \ \ BLOCK BLKID 
= MIXREC BLKTYPE = "MIXER" MDLTYPE = "Mixer" IN = ( S2 M0-1 RECYCLE M0-1 ) OUT 
= ( S3 M0-1 ) \ \ BLOCK BLKID = "RX-STAGE" BLKTYPE = "RSTOIC" MDLTYPE = 
"RStoic" IN = ( S3 M0-1 ) OUT = ( S4 M0-1 ) \ \ BLOCK BLKID = COL1 BLKTYPE = 
"RADFRAC" MDLTYPE = "RadFrac" IN = ( S4 M0-1 ) OUT = ( DIST M1-2 BTMS M2-3 ) \ 
\ BLOCK BLKID = SPLIT1 BLKTYPE = "FSPLIT" MDLTYPE = "FSplit" IN = ( BTMS M0-1 ) 
OUT = ( PURGE M0-1 RECYCLE M0-1 ) \ \ BLOCK BLKID = GASCOMP BLKTYPE = "COMPR" 
MDLTYPE = "Compr" IN = ( N2FEED M0-1 ) OUT = ( GASHP M0-1 ) \ ? STREAM MATERIAL 
FEED ? ; "METCBAR_MOLE" ; \ SUBSTREAM SSID = MIXED TEMP = 30. PRES = 1.01325 \ 
? STREAM MATERIAL N2FEED ? ; "METCBAR_MOLE" ; \ SUBSTREAM SSID = MIXED TEMP = 
25. PRES = 1.01325 \ ? STREAM MATERIAL RECYCLE ? ; "METCBAR_MOLE" ; \ SUBSTREAM 
SSID = MIXED TEMP = 104. PRES = 1.2 \ ? BLOCK RSTOIC "RX-STAGE" ? ; 
"METCBAR_MOLE" ; \ PARAM TEMP = 150. PRES = 1.1 \ ? BLOCK RADFRAC COL1 ? ; 
"METCBAR_MOLE" ; \ PARAM NSTAGE = 18 \ ? REACTIONS "R-COND" "REAC-DIST" ? \ 
STOIC REACNO = 1 STOIC-CID = ACETONE COEF = -2. <0> <0> / REACNO = 1 STOIC-CID 
= HEAVY COEF = 1. <0> <0> / REACNO = 1 STOIC-CID = WATER COEF = 1. <0> <0> \ ? 
CALCULATOR RATIO ? ; "METCBAR_MOLE" ; \ DEFINE FVN = FIPA FVN-VARTYPE = 
"MOLE-FLOW" FVN-STREAM = S2 FVN-SUBS = MIXED FVN-COMPONEN = IPA \ \ DEFINE FVN 
= XEXT FVN-VARTYPE = "BLOCK-VAR" FVN-BLOCK = "RX-STAGE" FVN-VARIABLE = CONV 
FVN-SENTENCE = CONV FVN-ID1 = 1 \ \ DEFINE FVN = FSPARE FVN-VARTYPE = 
"MOLE-FLOW" FVN-STREAM = S2 FVN-SUBS = MIXED FVN-COMPONEN = WATER \ \ FORTRAN 
FORTRAN-EXEC = ( "      XEXT = 0.75D0 + 0.0D0 * FIPA" ) \ ? "DESIGN-SPEC" 
"DS-PUR" ? ; "METCBAR_MOLE" ; \ DEFINE FVN = XACE FVN-VARTYPE = "MOLE-FRAC" 
FVN-STREAM = DIST FVN-SUBS = MIXED FVN-COMPONEN = ACETONE \ \ SPEC EXPR1 = 
"XACE" EXPR2 = "0.5" \ ? "DESIGN-SPEC" "DS-RR" ? \ DEFINE FVN = RRNOW 
FVN-VARTYPE = "BLOCK-VAR" FVN-BLOCK = COL1 \ ? "CONV-OPTIONS" ? \ PARAM 
TEAR-METHOD = WEGSTEIN CHECKSEQ = NO \ \ WEGSTEIN WEG-MAXIT = 100 WEG-QMIN = 
-5. <0> <0> WEG-QMAX = 0. <0> <0> \ ? TEAR ? \ TEAR SID = RECYCLE \ ? DISABLE ? 
\ "DESIGN-SPEC" LIST = ( "DS-PUR" "DS-RR" ) \ 
 GRAPHICS_BACKUP
PFS V 5.00
$_SUMMARY_FILE
 DSET RUN-STATUS VERS @VERS ( "39.0" "WIN-X64" "" "" "" )
 DSET RUN-STATUS IT @IT ( "MAY 12, 2026  09:40:55 A.M." "_7350klm.inm" 4)
 DSET RUN-STATUS RUNID @RUNID ("_7350klm")
 DSET RUN-STATUS SP @SP ( "MAY 12, 2026 09:40:55 A.M." )
 DSET RUN-STATUS ERRTXT @L_12 (
 "The following messages were issued during Input Translation:"
 ""
 "   INFORMATION"
 "   HENRY COMPONENTS ARE DEFINED: THE BINARY DATABANK IS SEARCHED FOR"
 "   THEIR HENRY CONSTANTS."
 )
 DSET RUN-STATUS TOTSTAT @TSTAT (0)
"""

SOLVREC_FILES = {"SolvRec.his": SOLVREC_HIS, "solvrec.rep": SOLVREC_REP, "SolvRec.cpm": SOLVREC_CPM,
                 "SolvRec.bkp": SOLVREC_BKP}


def write_solvrec(folder: Path) -> Path:
    """The four files of the synthetic case in one version folder (CRLF, ANSI like Aspen writes)."""
    for name, text in SOLVREC_FILES.items():
        write(folder / name, text)
    return folder
