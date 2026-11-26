import sys
import os
SKILL = os.environ.get("OCI_DIAGRAM_SKILL", "oci-architecture-diagrams")  # folder with scripts/ocidraw.py and the OCI toolkit
sys.path.insert(0, SKILL+"/scripts")
from ocidraw import Diagram
d = Diagram(title="Extend FLEXCUBE on OCI - logical")
d.text("Extend Oracle FLEXCUBE with AI on OCI: logical architecture", 0, 0, 900, 24, size=16, bold=True)
src = d.group("onprem", "FLEXCUBE (unchanged), read a copy", 0, 50, 240, 470)
s = [d.box(t, 20, 50+i*100, 200, 70, parent=src, kind="onprem_component") for i, t in enumerate(
    ["FLEXCUBE on OCI\nstandby or refreshable clone", "On premises\nGoldenGate or Data Guard", "Exadata Cloud@Customer or\nOracle Database@Azure", "Sample bank\nAutonomous AI Database"])]
oc = d.group("other", "Oracle Cloud Infrastructure", 290, 50, 1010, 640)
aidp = d.group("other", "Oracle AI Data Platform", 20, 40, 760, 580, parent=oc)
ext = d.box("External catalog\nread-only user", 20, 60, 150, 60, parent=aidp, kind="atomic")
fnd = d.group("other", "Shared data foundation", 200, 40, 260, 230, parent=aidp)
br = d.box("Bronze\nFLEXCUBE tables, lineage", 20, 40, 220, 50, parent=fnd, kind="atomic")
si = d.box("Silver: customer 360, accounts,\ntransactions, loans, cards", 20, 100, 220, 55, parent=fnd, kind="atomic")
qg = d.box("Quality gate", 20, 165, 220, 45, parent=fnd, kind="atomic")
mods = d.group("other", "Use-case modules (gold, ML, gates)", 490, 40, 250, 330, parent=aidp)
m = [d.box(t, 20, 45+i*70, 210, 55, parent=mods, kind="atomic" if i == 0 else "optional") for i, t in enumerate(
    ["01 Cash-flow intelligence", "02 Reconciliation watch", "03 FLEXCUBE data copilot", "04 SME supply chain\nand life events"])]
ml = d.box("MLflow experiments\nand model registry", 200, 300, 260, 60, parent=aidp, kind="atomic")
wf = d.box("Workflows: daily run\nafter end of day", 20, 300, 150, 60, parent=aidp, kind="atomic")
ag = d.box("Agents with tools,\nmemory and guardrails", 810, 450, 180, 80, parent=oc, kind="atomic")
al = d.box("Alert tasks", 20, 510, 440, 50, parent=aidp, kind="atomic")
sv = d.box("Serving layer: AIDP Lakehouse\nread-only agent user", 490, 430, 250, 60, parent=aidp, kind="atomic")
gai = d.box("OCI Generative AI", 810, 560, 180, 50, parent=oc, kind="atomic")
ops = d.box("Vault, IAM, Logging,\nNotifications", 20, 420, 440, 60, parent=aidp, kind="atomic")
ch = d.group("thirdparty", "People and channels", 1340, 50, 220, 640)
u1 = d.box("Agent Hub and\napps via /chat API", 20, 465, 180, 50, parent=ch, kind="thirdparty_component")
u3 = d.box("Slack or Teams", 20, 560, 180, 50, parent=ch, kind="thirdparty_component")
d.connect(src, ext, label="JDBC, private")
d.connect(ext, br); d.connect(br, si); d.connect(si, qg)
d.connect(qg, mods)
d.connect(mods, ml, both=True)
d.connect(mods, sv, label="publish")
d.connect(sv, ag, label="read-only")
d.connect(ag, gai)
d.connect(ag, u1)
d.connect(al, u3, exit=(0.5,1), waypoints=[(550,680),(1450,680)], entry=(0.5,1))
print(d.check()); d.save("logical-overview.drawio"); d.render("logical-overview.png")
