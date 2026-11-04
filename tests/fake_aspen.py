"""A fake Aspen Plus automation server for offline tests of fwlib.com (no pywin32, no Aspen).

The tree has the shape the help describes (Data > Streams and Blocks > Input, Output, Ports;
Results Summary > Run-Status > Output). Names and values are invented.
"""
from __future__ import annotations

from pathlib import Path

import samples

ENTERABLE = 7                     # attribute number used by the fake for HAP_ENTERABLE
CONSTANTS = {"IAP_REINIT_SIMULATION": 3, "HAP_ENTERABLE": ENTERABLE}
PORTS = {"HEATER": ["F(IN)", "P(OUT)"], "RSTOIC": ["F(IN)", "P(OUT)"], "MIXER": ["F(IN)", "P(OUT)"],
         "RADFRAC": ["F(IN)", "LD(OUT)", "B(OUT)", "VD(OUT)"]}


class Coll:
    def __init__(self, owner, items=()):
        self.owner = owner
        self.items = list(items)
        for i in self.items:
            i.parent = owner

    def __iter__(self):
        return iter(list(self.items))

    @property
    def Count(self):
        return len(self.items)

    def Item(self, key):
        if isinstance(key, int):
            return self.items[key]
        for i in self.items:
            if i.Name.upper() == str(key).upper():
                return i
        raise KeyError(key)

    __call__ = Item

    def Add(self, spec):
        return self.owner.server.on_add(self.owner, spec)

    def Remove(self, name):
        return self.owner.server.on_remove(self.owner, name)


class Node:
    def __init__(self, server, name, value=None, unit="", enterable=True, kids=()):
        self.server, self.Name, self._value, self.UnitString = server, name, value, unit
        self.enterable = enterable
        self.parent = None
        self.Elements = Coll(self, kids)

    @property
    def Value(self):
        return self._value

    @Value.setter
    def Value(self, v):
        if v == "rejected":
            raise ValueError("Aspen does not accept this value")
        self._value = v

    def AttributeValue(self, n):
        if n == ENTERABLE:
            return self.enterable
        raise ValueError(f"no attribute {n}")


class PortNode(Node):
    """A port whose connect member is either Add on the port (the help's form) or Elements.Add."""

    def __init__(self, server, name, streams=(), direct=True):
        super().__init__(server, name, kids=[Node(server, s) for s in streams])
        if direct:
            self.Add = lambda s: server.on_add(self, s)
            self.Remove = lambda s: server.on_remove(self, s)


class Engine:
    def __init__(self, server):
        self.server = server
        self.polls_left = 0
        self.running = False
        self.stops = 0
        self.reinits = []

    @property
    def IsRunning(self):
        if not self.server.has_is_running:
            raise AttributeError("IsRunning")
        if self.running:
            if self.polls_left is not None:
                self.polls_left -= 1
                if self.polls_left <= 0:
                    self.running = False
                    self.server.finish_run()
        return self.running

    def Run2(self, async_):
        self.server.runs.append(async_)
        if self.server.fail_run:
            raise RuntimeError("the engine stopped with an internal error")
        if not async_:
            self.server.finish_run()
            return
        self.running = True
        self.polls_left = self.server.run_polls

    def Stop(self):
        self.stops += 1
        self.running = False

    def Reinit(self, what=None):
        self.reinits.append(what)


class FakeAspen:
    """The Apwn.Document object."""

    def __init__(self, run_polls=3, fail_run=False, has_is_running=True, direct_ports=True, version="41.0"):
        self.run_polls, self.fail_run, self.has_is_running = run_polls, fail_run, has_is_running
        self.direct_ports = direct_ports
        self.Version = version
        self.Visible = 0
        self.SuppressDialogs = 0
        self.opened = []
        self.exports = []
        self.quit = 0
        self.runs = []
        self.results = False
        self.Engine = Engine(self)
        self.Tree = self._tree()

    # tree -----------------------------------------------------------------
    def _stream(self, name, temp=25.0):
        return Node(self, name, kids=[
            Node(self, "Input", kids=[Node(self, "TEMP", kids=[Node(self, "MIXED", temp, "C")]),
                                      Node(self, "PRES", kids=[Node(self, "MIXED", 1.01325, "bar")]),
                                      Node(self, "TOTFLOW", kids=[Node(self, "MIXED", 100.0, "kmol/hr")])]),
            Node(self, "Output", kids=[Node(self, "TEMP_OUT", kids=[Node(self, "MIXED", None, "C", enterable=False)])])])

    def _block(self, name, typ, temp=40.0):
        ports = [PortNode(self, p, direct=self.direct_ports) for p in PORTS.get(typ, ["F(IN)", "P(OUT)"])]
        return Node(self, name, kids=[
            Node(self, "Input", kids=[Node(self, "TEMP", temp, "C"), Node(self, "PRES", 0.0, "bar"),
                                      Node(self, "CALC", 1.0, "", enterable=False)]),
            Node(self, "Output", kids=[Node(self, "QCALC", None, "cal/sec", enterable=False)]),
            Node(self, "Ports", kids=ports)])

    def _tree(self):
        r1 = self._block("R1", "RSTOIC")
        r1.Elements.Item("Ports").Elements.Item("F(IN)").Elements.items.append(Node(self, "FEED"))
        r1.Elements.Item("Ports").Elements.Item("P(OUT)").Elements.items.append(Node(self, "PROD"))
        status = Node(self, "Run-Status", kids=[Node(self, "Output", kids=[
            Node(self, f, None) for f in ("CVSTAT", "RSTAT", "PPSTAT")])])
        data = Node(self, "Data", kids=[
            Node(self, "Streams", kids=[self._stream("FEED"), self._stream("PROD")]),
            Node(self, "Blocks", kids=[r1]),
            Node(self, "Results Summary", kids=[status])])
        root = Node(self, "Root", kids=[data])
        root.FindNode = self.find
        return root

    def find(self, path):
        node = self.Tree
        for part in [p for p in path.split("\\") if p]:
            try:
                node = node.Elements.Item(part)
            except KeyError:
                return None
        return node

    def on_add(self, owner, spec):
        name, _, typ = spec.partition("!")
        if owner.Name == "Blocks":
            owner.Elements.items.append(self._block(name, typ.upper()))
        elif owner.Name == "Streams":
            owner.Elements.items.append(self._stream(name))
        elif isinstance(owner, PortNode):
            owner.Elements.items.append(Node(self, name))
        else:
            raise ValueError(f"cannot add to {owner.Name}")

    def on_remove(self, owner, name):
        before = len(owner.Elements.items)
        owner.Elements.items = [i for i in owner.Elements.items if i.Name.upper() != name.upper()]
        if len(owner.Elements.items) == before:
            raise ValueError(f"{name} not found")

    def finish_run(self):
        """Results: PROD leaves at the block temperature; above 500 C the run has errors."""
        t = self.find("\\Data\\Blocks\\R1\\Input\\TEMP").Value
        self.find("\\Data\\Streams\\PROD\\Output\\TEMP_OUT\\MIXED")._value = t
        self.find("\\Data\\Blocks\\R1\\Output\\QCALC")._value = -12345.6
        flags = self.find(r"\Data\Results Summary\Run-Status\Output")
        for f in flags.Elements:
            f._value = 1 if (f.Name == "CVSTAT" and t > 500) else 0
        self.results = True

    # files ----------------------------------------------------------------
    def InitFromArchive2(self, path, *a):
        if not Path(path).is_file():
            raise OSError(f"cannot open {path}")
        self.opened.append(path)

    InitFromFile2 = InitFromArchive2

    def Export(self, kind, path):
        self.exports.append((kind, Path(path).name))
        p = Path(path)
        names = [b.Name for b in self.find("\\Data\\Blocks").Elements]
        if kind == 1:
            text = ('MM "41.0" FLAVOR "NO" VERSION "41.0" DATETIME "Tue Mar  3 10:16:00 2026"\n'
                    + "".join(f"; block {n}\n" for n in names))
            if self.results:
                text += ('$_SUMMARY_FILE\n DSET RUN-STATUS IT @IT ( "MARCH 3, 2026  10:15:40 A.M." '
                         '"_1234abc.inm" 4)\n')
            p.write_text(text, encoding="latin-1")
        elif kind == 2:
            if not self.results:
                raise RuntimeError("no results in this session")
            samples.write(p, samples.rep_at("MARCH 3, 2026", "10:15:40 A.M."))
        elif kind == 6:
            samples.write(p, samples.CPM)
        elif kind == 18:
            p.write_text("".join(f"BLOCK {n}\n" for n in names), encoding="latin-1")
        else:
            raise RuntimeError(f"export type {kind} not supported by the fake")

    def WriteArchive2(self, path, *a):
        self.Export(1, path)

    def Quit(self):
        self.quit += 1


class Clock:
    """Time that moves only when the code under test sleeps."""

    def __init__(self):
        self.t = 0.0

    def now(self):
        return self.t

    def sleep(self, s):
        self.t += s


def factory(server: FakeAspen, clock: Clock = None, constants=None):
    from fwlib import com
    clock = clock or Clock()

    def make(visible=False):
        server.Visible = 1 if visible else 0
        server.SuppressDialogs = 1
        return com.Aspen(server, constants=CONSTANTS if constants is None else constants, sleep=clock.sleep,
                         clock=clock.now)
    return make
