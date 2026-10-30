"""Fictional company database for Rimal Engineering & Technology. All people, projects and emails are synthetic."""
from datetime import datetime, date, timedelta

from .db import Base, engine, SessionLocal
from .models import (Department, Role, Project, Employee, User, CompanyEmail, CompanyDocument, Course, JSONMixin)
from .auth import hash_password

J = JSONMixin.dump

DEPARTMENTS = {
    "Electrical Engineering": "Designs, installs and commissions power distribution and substation systems for our clients.",
    "Project Management Office": "Plans, schedules and controls project delivery, cost and client reporting.",
    "Digital & Software": "Builds the software, automation and data platforms that monitor our engineered systems.",
    "Procurement": "Sources, qualifies and expedites equipment and materials for all projects.",
    "Human Resources": "Recruits, onboards and supports our people.",
}

SK = lambda key, name, kws: {"key": key, "name": name, "keywords": kws}

ROLES = [
    dict(title="Electrical Project Engineer", dept="Electrical Engineering",
         summary="Delivers the electrical scope of client projects: design reviews, site coordination, inspections, testing and handover documentation.",
         skills=[SK("power", "Power systems & substations", ["substation", "power system", "switchgear", "transformer", "33kv", "132kv", "mv ", "lv ", "medium voltage", "power distribution"]),
                 SK("cad", "Electrical design (AutoCAD / ETAP)", ["autocad", "etap", "single line", "sld", "dialux", "revit"]),
                 SK("testing", "Testing & commissioning", ["commissioning", "testing", " test", "inspection", "itp", " fat ", " sat ", "relay", "protection", "megger"]),
                 SK("coord", "Project coordination & scheduling", ["schedule", "primavera", " p6", "ms project", "coordinat", "planning", "gantt", "subcontractor", "look-ahead"]),
                 SK("docs", "Technical documentation & document control", ["document control", "document register", "submittal", " rfi", "method statement", "as-built", "documentation", "aconex"]),
                 SK("safety", "Site safety (HSE)", ["hse", "safety", "permit to work", "loto", "osha", "risk assessment"]),
                 SK("software", "Software & automation", ["python", "c++", "embedded", " plc", "scada", "programming", "automation", "matlab"])],
         responsibilities=[
             {"title": "Review electrical design submittals", "detail": "Check single-line diagrams, cable schedules and load calculations against client specs before submission.", "skills": ["power", "cad"]},
             {"title": "Prepare inspection & test plans (ITPs)", "detail": "Draft ITPs and coordinate witness points with the client's inspector.", "skills": ["testing", "docs"]},
             {"title": "Coordinate site activities with subcontractors", "detail": "Track installation progress, look-ahead schedules and resolve site clashes.", "skills": ["coord", "safety"]},
             {"title": "Maintain the project document register", "detail": "Keep submittals, RFIs and revisions current so inspections never fail on paperwork.", "skills": ["docs"]},
             {"title": "Support SCADA / protection integration", "detail": "Work with the Digital team on relay settings export and SCADA point lists.", "skills": ["software", "testing"]},
         ],
         equipment=[{"item": "Engineering laptop (32 GB RAM, dedicated GPU)", "kind": "hardware", "reason": "AutoCAD Electrical and ETAP need a workstation-class machine."},
                    {"item": "Site PPE kit (helmet, FR coveralls, safety boots, arc-rated gloves)", "kind": "hardware", "reason": "Role requires regular substation site visits."},
                    {"item": "Site access card for assigned project", "kind": "access", "reason": "Needed to enter the client's restricted energised area."},
                    {"item": "AutoCAD Electrical licence", "kind": "software", "reason": "Design review and mark-ups of SLDs."},
                    {"item": "ETAP viewer licence", "kind": "software", "reason": "Review load-flow and short-circuit studies."},
                    {"item": "Aconex document-control account", "kind": "access", "reason": "All submittals and RFIs are exchanged with the client through Aconex."},
                    {"item": "Primavera P6 (read access)", "kind": "software", "reason": "Follow the project schedule and look-aheads."}],
         example={"title": "Pre-inspection document register check",
                  "scenario": "The client has scheduled an inspection of Feeder Bay 3 on Thursday. Before then, review the document register and flag anything missing or outdated.",
                  "steps": ["Open the document register for Feeder Bay 3", "Compare each drawing's revision against the latest approved submittal", "Flag the cable schedule still at Rev B when Rev C was approved", "Confirm the ITP for relay testing is signed by the client", "Send a short status note to the project manager"],
                  "deliverable": "A one-page readiness note listing missing or outdated documents and owners."}),
    dict(title="Software Engineer", dept="Digital & Software",
         summary="Builds and maintains the monitoring software, APIs and dashboards behind our energy and building automation projects.",
         skills=[SK("python", "Python & backend APIs", ["python", "fastapi", "django", "flask", "api", "rest"]),
                 SK("frontend", "Web frontend (React / TypeScript)", ["react", "typescript", "javascript", "frontend", "vue", "angular"]),
                 SK("data", "Databases & data pipelines", ["sql", "postgres", "database", "etl", "pipeline", "timeseries", "influx"]),
                 SK("iot", "IoT / SCADA protocols", ["mqtt", "modbus", "bacnet", "scada", "iot", "opc", "plc"]),
                 SK("devops", "Cloud & DevOps", ["docker", "kubernetes", "ci/cd", "aws", "azure", "devops", "linux"]),
                 SK("swtest", "Automated testing", ["pytest", "unit test", "testing", "tdd", "jest"])],
         responsibilities=[
             {"title": "Extend the building telemetry API", "detail": "Add endpoints for new BMS points on the King Fahd Tower retrofit.", "skills": ["python", "data"]},
             {"title": "Integrate BACnet/Modbus devices", "detail": "Map field device points into the telemetry platform.", "skills": ["iot"]},
             {"title": "Build client dashboard views", "detail": "React views for energy, alarms and comfort KPIs.", "skills": ["frontend"]},
             {"title": "Keep CI green and deployments safe", "detail": "Write tests and maintain the deployment pipeline.", "skills": ["swtest", "devops"]},
         ],
         equipment=[{"item": "Developer laptop (MacBook Pro, 32 GB)", "kind": "hardware", "reason": "Local containers and builds."},
                    {"item": "GitLab account + repository access", "kind": "access", "reason": "All source code lives in GitLab."},
                    {"item": "VPN certificate", "kind": "access", "reason": "Reach staging and on-site gateways."},
                    {"item": "Docker Desktop licence", "kind": "software", "reason": "Run the platform locally."},
                    {"item": "BACnet/Modbus test gateway (lab)", "kind": "hardware", "reason": "Test device integrations safely."}],
         example={"title": "Add a new BMS point to the telemetry API",
                  "scenario": "Facilities wants chilled-water supply temperature from AHU-7 on the dashboard.",
                  "steps": ["Find the BACnet object ID in the point list", "Add the mapping in the ingestion config", "Expose it in the /points API", "Write a test with a recorded sample", "Open a merge request for review"],
                  "deliverable": "A merged change with a passing test and the new point visible on staging."}),
    dict(title="Project Coordinator", dept="Project Management Office",
         summary="Keeps project schedules, meetings, risks and client reporting under control.",
         skills=[SK("sched", "Scheduling (Primavera / MS Project)", ["primavera", "p6", "ms project", "schedule", "gantt"]),
                 SK("report", "Client reporting", ["report", "kpi", "dashboard", "excel", "power bi"]),
                 SK("risk", "Risk & issue management", ["risk", "issue log", "mitigation", "raid"]),
                 SK("comm", "Stakeholder communication", ["stakeholder", "client", "communication", "meeting", "minutes"]),
                 SK("docs", "Document control", ["document control", "aconex", "submittal", "rfi"])],
         responsibilities=[
             {"title": "Update the weekly look-ahead schedule", "detail": "Collect progress from engineers and update P6.", "skills": ["sched"]},
             {"title": "Prepare the monthly client report", "detail": "Progress, KPIs, risks and photos.", "skills": ["report", "comm"]},
             {"title": "Run the RAID log", "detail": "Track risks, actions, issues, decisions.", "skills": ["risk"]},
         ],
         equipment=[{"item": "Standard laptop (16 GB)", "kind": "hardware", "reason": "Office and reporting tools."},
                    {"item": "Primavera P6 licence", "kind": "software", "reason": "Schedule updates."},
                    {"item": "Power BI Pro licence", "kind": "software", "reason": "Client KPI dashboards."},
                    {"item": "Aconex account", "kind": "access", "reason": "Client correspondence."}],
         example={"title": "Weekly look-ahead update",
                  "scenario": "Two cable-pulling activities slipped by three days.",
                  "steps": ["Collect updates from site", "Update actual dates in P6", "Check the critical path impact", "Flag the slip in the RAID log", "Share the look-ahead with the PM"],
                  "deliverable": "Updated 3-week look-ahead with the slip explained."}),
]

PROJECTS = [
    dict(code="NSU", name="Al Noor 132/33 kV Substation Upgrade", client="Eastern Grid Utility (fictional)", phase="Installation & testing",
         background="Upgrade of the Al Noor substation from 2 to 4 transformer bays to serve the new industrial zone. Rimal is the EPC contractor for the electrical scope.",
         objectives=["Energise transformer bays 3 and 4 by Q1 2027", "Zero lost-time incidents", "Pass all client inspections first time"],
         deliverables=["Approved design submittals", "Inspection & test plans", "Commissioning records", "As-built drawings"]),
    dict(code="MDP", name="Metro Line 4 Depot Power Supply", client="City Transit Authority (fictional)", phase="Design",
         background="Design and supply of the 33 kV/LV distribution and traction auxiliary supply for the Line 4 maintenance depot.",
         objectives=["Issue IFC design package by December 2026", "Finalise switchgear vendor"],
         deliverables=["IFC drawings", "Load-flow study", "Switchgear technical evaluation"]),
    dict(code="KFT", name="King Fahd Tower BMS & Energy Retrofit", client="Tower Facilities Co. (fictional)", phase="Implementation",
         background="Retrofit of the 42-floor tower's building management system with a new energy monitoring platform built by Rimal Digital.",
         objectives=["Cut HVAC energy use 15%", "Migrate 3,200 BMS points to the new platform"],
         deliverables=["Telemetry platform", "Energy dashboard", "Point migration report"]),
]

# (code, name, email, title, role, dept, manager_code, project)
PEOPLE = [
    ("R-0001", "Faisal Al-Harbi", "faisal.alharbi@rimal.example", "Chief Executive Officer", None, "Project Management Office", None, None),
    ("R-0010", "Noura Al-Qahtani", "noura.alqahtani@rimal.example", "HR Manager", None, "Human Resources", "R-0001", None),
    ("R-0020", "Khalid Al-Mutairi", "khalid.almutairi@rimal.example", "Head of Electrical Engineering", None, "Electrical Engineering", "R-0001", "NSU"),
    ("R-0021", "Omar Haddad", "omar.haddad@rimal.example", "Senior Electrical Engineer", "Electrical Project Engineer", "Electrical Engineering", "R-0020", "NSU"),
    ("R-0022", "Lina Saeed", "lina.saeed@rimal.example", "Electrical Project Engineer", "Electrical Project Engineer", "Electrical Engineering", "R-0020", "NSU"),
    ("R-0023", "Tariq Al-Shehri", "tariq.alshehri@rimal.example", "Protection & Testing Engineer", "Electrical Project Engineer", "Electrical Engineering", "R-0020", "MDP"),
    ("R-0030", "Reem Al-Zahrani", "reem.alzahrani@rimal.example", "Head of PMO", None, "Project Management Office", "R-0001", None),
    ("R-0031", "Yousef Nasser", "yousef.nasser@rimal.example", "Project Manager — Al Noor", "Project Coordinator", "Project Management Office", "R-0030", "NSU"),
    ("R-0032", "Dana Al-Ghamdi", "dana.alghamdi@rimal.example", "Project Manager — Metro Depot", "Project Coordinator", "Project Management Office", "R-0030", "MDP"),
    ("R-0040", "Hassan Ali", "hassan.ali@rimal.example", "Head of Digital & Software", None, "Digital & Software", "R-0001", "KFT"),
    ("R-0041", "Sara Mansour", "sara.mansour@rimal.example", "Senior Software Engineer", "Software Engineer", "Digital & Software", "R-0040", "KFT"),
    ("R-0042", "Ahmed Karim", "ahmed.karim@rimal.example", "IoT Integration Engineer", "Software Engineer", "Digital & Software", "R-0040", "KFT"),
    ("R-0050", "Majed Al-Otaibi", "majed.alotaibi@rimal.example", "Procurement Lead", None, "Procurement", "R-0001", None),
    ("R-0060", "Ibrahim Saleh", "ibrahim.saleh@rimal.example", "IT Support Lead", None, "Digital & Software", "R-0040", None),
]

BIOS = {
    "R-0021": "15 years in substations; mentors new engineers on testing & commissioning. Go-to for relay protection questions.",
    "R-0022": "Handles document control and client inspections on Al Noor.",
    "R-0023": "Protection relay and testing specialist; currently on Metro Depot design.",
    "R-0031": "Runs the Al Noor project day to day; chairs the Monday coordination meeting.",
    "R-0041": "Leads the telemetry platform; mentors new developers.",
    "R-0042": "BACnet/Modbus integration on King Fahd Tower.",
    "R-0060": "Contact for laptops, licences, VPN and accounts.",
    "R-0050": "Contact for vendor selection and purchase orders.",
}

d = lambda s: datetime.fromisoformat(s)
EMAILS = [
    ("NSU", "yousef.nasser@rimal.example", "Al Noor project team", "Kick-off: Bays 3 & 4 installation phase", "2026-08-03T09:00",
     "Team,\n\nWe start installation of transformer bays 3 and 4 next week. Priorities:\n1. Civil handover of Bay 3 foundations (done 30 July).\n2. Switchgear delivery from vendor expected 20 August.\n3. Client wants weekly progress photos every Thursday.\n\nMonday 8:30 coordination meeting is mandatory for all engineers on site.\n\nYousef"),
    ("NSU", "khalid.almutairi@rimal.example", "Yousef Nasser; Omar Haddad; Majed Al-Otaibi", "Decision: switching 33 kV cable supplier", "2026-08-14T14:20",
     "All,\n\nWe are moving the 33 kV XLPE cable order from Supplier A to Supplier B. Reason: Supplier A's type-test certificates for the 630 mm² size expired and they cannot renew before October, which would delay energisation by ~6 weeks. Supplier B has valid certificates and can deliver in 5 weeks at +3% cost, which the client approved in writing (see Aconex letter EGU-L-0457).\n\nThis decision is logged in the Al Noor decision log as D-012.\n\nKhalid"),
    ("NSU", "lina.saeed@rimal.example", "Yousef Nasser; Omar Haddad", "Inspection failed: Feeder Bay 1 — outdated cable schedule", "2026-08-27T16:05",
     "Hi both,\n\nThe client inspector rejected the Feeder Bay 1 inspection today because the cable schedule on site was Rev B while Rev C had been approved. No technical defect — purely a document control issue.\n\nAction: from now on I will run a document register check 48 hours before every inspection. Re-inspection booked for 3 Sept.\n\nLina"),
    ("NSU", "yousef.nasser@rimal.example", "Al Noor project team", "Lesson learned: 48-hour pre-inspection register check", "2026-09-04T10:00",
     "Following the Feeder Bay 1 rejection, the pre-inspection document register check is now mandatory 48 h before any client inspection. Re-inspection on 3 Sept passed first time. New engineers: please learn this procedure (PROC-NSU-07).\n\nYousef"),
    ("NSU", "omar.haddad@rimal.example", "Tariq Al-Shehri; Khalid Al-Mutairi", "Relay settings for Bay 3 — protection coordination", "2026-09-18T11:30",
     "Tariq,\n\nI've reviewed the relay settings for the Bay 3 transformer differential protection. The slope settings follow the client's protection philosophy PP-04. Please export the settings files to the Digital team so the SCADA point list can be updated — they need IEC 61850 names by 1 October.\n\nOmar"),
    ("NSU", "yousef.nasser@rimal.example", "Eastern Grid Utility (client)", "Monthly report — September 2026", "2026-10-02T09:00",
     "Dear Client,\n\nSeptember summary: Bay 3 switchgear installed (100%), cable pulling 65%, Bay 4 foundations 80%. One inspection rejected and re-passed (document revision issue, procedure improved). Forecast energisation of Bay 3: 15 January 2027. No safety incidents.\n\nRegards, Yousef Nasser"),
    ("NSU", "khalid.almutairi@rimal.example", "Al Noor project team", "Upcoming: Bay 3 FAT witness at vendor works", "2026-10-20T08:45",
     "The factory acceptance test for the Bay 3 protection panels is on 12 November at the vendor's works. Omar leads; one new engineer may attend as an observer for learning. Please make sure the ITP-NSU-14 is signed off before travel.\n\nKhalid"),
    ("MDP", "dana.alghamdi@rimal.example", "Metro Depot team", "Switchgear vendor shortlist", "2026-09-10T13:00",
     "Shortlisted vendors for 33 kV switchgear: Vendor X and Vendor Y. Technical evaluation due 30 September. Tariq owns the technical scoring sheet; Majed is running the commercial side.\n\nDana"),
    ("MDP", "tariq.alshehri@rimal.example", "Dana Al-Ghamdi; Khalid Al-Mutairi", "Technical evaluation result — Vendor Y recommended", "2026-09-29T17:10",
     "Vendor Y scored 86 vs 78 for Vendor X. Main reasons: lower arc-flash incident energy rating design, and local service centre within 50 km of the depot. Vendor X was cheaper by 4% but failed the internal-arc classification requirement IAC AFLR 31.5 kA.\n\nTariq"),
    ("MDP", "dana.alghamdi@rimal.example", "Metro Depot team", "Design freeze date moved to 5 December", "2026-10-15T10:30",
     "The client asked for two extra EV charging feeders in the depot, so the IFC design freeze moves from 20 November to 5 December. Load-flow study must be re-run with the additional 2 x 350 kW load.\n\nDana"),
    ("KFT", "hassan.ali@rimal.example", "Digital team", "Why we chose TimescaleDB for telemetry", "2026-07-22T15:00",
     "We evaluated InfluxDB and TimescaleDB for the King Fahd Tower platform. We chose TimescaleDB because the team already knows PostgreSQL, we need relational joins with the asset register, and the client's IT only supports PostgreSQL in their backup policy.\n\nHassan"),
    ("KFT", "sara.mansour@rimal.example", "Digital team", "Point migration progress: 1,900 / 3,200", "2026-10-08T12:00",
     "We've migrated 1,900 of 3,200 BMS points. Floors 1–25 done. Blocker: floors 26–42 use an older BACnet MS/TP trunk that needs a new router — Ibrahim has ordered it, ETA 4 November.\n\nSara"),
    ("KFT", "ahmed.karim@rimal.example", "Sara Mansour", "AHU-7 chilled water sensor drift", "2026-10-21T09:40",
     "AHU-7 supply temperature reads 2.1°C higher than the handheld reference. I added a calibration offset in the ingestion config and raised a maintenance ticket with facilities (FM-2291).\n\nAhmed"),
    (None, "noura.alqahtani@rimal.example", "All staff", "Reminder: annual Code of Conduct acknowledgement", "2026-09-01T08:00",
     "All employees (including new joiners within 30 days of start) must read and acknowledge the Code of Conduct in the HR portal. Working hours are Sunday–Thursday 8:00–17:00. Contact HR for any questions.\n\nNoura"),
    (None, "ibrahim.saleh@rimal.example", "All staff", "IT: MFA now mandatory", "2026-09-15T09:00",
     "Multi-factor authentication is mandatory for email, VPN and Aconex from 1 October. New joiners: IT will set up MFA on day one. Laptop requests go through the IT service desk.\n\nIbrahim"),
    (None, "faisal.alharbi@rimal.example", "All staff", "Rimal 2027 priorities", "2026-10-01T08:30",
     "Our three priorities for 2027: (1) safety first — zero lost-time incidents; (2) deliver Al Noor and Metro Depot on time; (3) grow Rimal Digital so every project we build can be monitored.\n\nFaisal"),
]

DOCS = [
    (None, "policy", "Employee Handbook (summary)", "Working week Sunday–Thursday, 8:00–17:00. Annual leave 30 days after probation. Probation 90 days. Dress code: business casual in office; full PPE on site. Expense claims within 30 days via HR portal."),
    (None, "policy", "IT Acceptable Use & Security", "Company laptops only for company data. MFA mandatory. Never share credentials. Report phishing to IT. Personal USB drives are blocked."),
    (None, "policy", "HSE Golden Rules", "1. Permit to work for all energised areas. 2. Lock-out/tag-out before maintenance. 3. Full PPE on site. 4. Stop work if unsafe. Site induction required before first visit."),
    ("NSU", "charter", "Al Noor Project Charter", "Scope: electrical EPC for Bays 3 & 4. Budget: SAR 48M. Key dates: Bay 3 energisation Jan 2027, Bay 4 May 2027. PM: Yousef Nasser. Engineering lead: Omar Haddad. Client: Eastern Grid Utility."),
    ("NSU", "decision-log", "Al Noor Decision Log", "D-009: Use GIS for Bay 4 (space constraints). D-011: Weekly progress photos on Thursdays (client request). D-012: Switch 33 kV cable supplier A→B due to expired type-test certificates; +3% cost approved by client (EGU-L-0457)."),
    ("NSU", "procedure", "PROC-NSU-07 Pre-inspection Document Register Check", "48 hours before any client inspection: 1) export document register, 2) compare drawing revisions with latest approved submittals, 3) verify ITP signatures, 4) print current revisions for site, 5) send readiness note to PM."),
    ("MDP", "charter", "Metro Depot Project Charter", "Scope: design & supply of 33 kV/LV distribution for the Line 4 depot. PM: Dana Al-Ghamdi. Technical lead: Tariq Al-Shehri. IFC design freeze: 5 Dec 2026 (moved)."),
    ("KFT", "charter", "King Fahd Tower Retrofit Charter", "Scope: new BMS telemetry platform and energy dashboard; 3,200 points. Lead: Hassan Ali; tech lead Sara Mansour. Target: 15% HVAC energy reduction."),
    ("KFT", "meeting-notes", "KFT Sprint Review — 23 Oct 2026", "Done: alarm dashboard v1, floors 1–25 migrated. Next: MS/TP router install (4 Nov), energy baseline report. Risk: client IT change freeze in December."),
]

COURSES = [
    ("ACAD-001", "Rimal Essentials: Orientation, Conduct, Safety & IT Security", ["orientation", "safety"], "Foundation", 3.0, True,
     "Who we are and how we work, the Code of Conduct, HSE golden rules and site induction, and IT security & MFA. Required for every new joiner."),
    ("ENG-101", "Substation Fundamentals for Project Engineers", ["power"], "Foundation", 6.0, False, "Bays, switchgear, transformers, protection basics at 132/33 kV."),
    ("ENG-110", "AutoCAD Electrical & ETAP for Design Review", ["cad"], "Intermediate", 8.0, False, "Reviewing SLDs, cable schedules and load-flow results."),
    ("ENG-120", "Testing & Commissioning: ITPs, FAT and SAT", ["testing", "docs"], "Intermediate", 5.0, False, "Writing ITPs, witnessing tests, commissioning records."),
    ("ENG-130", "Protection Relays & IEC 61850 Basics", ["testing", "software"], "Advanced", 6.0, False, "Relay settings, coordination and substation automation."),
    ("PM-101", "Project Scheduling with Primavera P6", ["coord", "sched"], "Foundation", 6.0, False, "Look-ahead schedules, critical path, progress updates."),
    ("PM-110", "Document Control & Aconex", ["docs"], "Foundation", 2.0, False, "Submittals, RFIs, revisions — and avoiding failed inspections."),
    ("PM-120", "Risk & Stakeholder Management", ["risk", "comm", "report"], "Intermediate", 4.0, False, "RAID logs, client communication, monthly reporting."),
    ("DIG-101", "Python for Engineers", ["software", "python"], "Foundation", 8.0, False, "Automating engineering calculations and reports."),
    ("DIG-110", "Telemetry Platform Onboarding (FastAPI + TimescaleDB)", ["python", "data"], "Intermediate", 4.0, False, "Architecture and codebase tour of our KFT platform."),
    ("DIG-120", "BACnet & Modbus Integration", ["iot"], "Intermediate", 5.0, False, "Point mapping, MS/TP vs IP, troubleshooting."),
    ("DIG-130", "React Dashboards at Rimal", ["frontend"], "Intermediate", 4.0, False, "Our component library and dashboard patterns."),
    ("DIG-140", "CI/CD, Docker & Testing Practices", ["devops", "swtest"], "Intermediate", 3.0, False, "How we test and ship safely."),
]

# External courses. Every URL was checked to load (HTTP 200) when this catalog was written.
EXTERNAL = [
    ("EXT-SIE", "Siemens Training Services — automation, SCADA, protection & power", "Siemens",
     "https://new.siemens.com/global/en/products/services/digital-enterprise-services/training-services.html",
     ["software", "iot", "testing", "power"], "Intermediate", "Vendor training on industrial automation, SCADA, protection and power distribution products."),
    ("EXT-ETAP", "ETAP Power System Training", "ETAP", "https://www.etap.com/training", ["power", "cad"], "Intermediate",
     "Official ETAP courses on load flow, short circuit and protection coordination studies."),
    ("EXT-PMF", "Foundations of Project Management", "Google via Coursera", "https://www.coursera.org/learn/project-management-foundations",
     ["coord", "sched", "risk", "comm", "report", "docs"], "Foundation", "Project roles, scope, stakeholders and planning basics."),
    ("EXT-PY", "Python for Everybody", "University of Michigan via Coursera", "https://www.coursera.org/specializations/python",
     ["software", "python"], "Foundation", "A gentle, practical introduction to programming in Python."),
    ("EXT-REACT", "Learn React", "react.dev (official docs)", "https://react.dev/learn", ["frontend"], "Foundation", "The official interactive React course."),
    ("EXT-DOCKER", "Docker: Get Started", "Docker (official docs)", "https://docs.docker.com/get-started/", ["devops", "swtest"], "Foundation", "Containers from first principles."),
    ("EXT-FASTAPI", "FastAPI Tutorial", "FastAPI (official docs)", "https://fastapi.tiangolo.com/tutorial/", ["python"], "Foundation", "Build typed Python APIs step by step."),
    ("EXT-PG", "PostgreSQL Tutorial", "PostgreSQL (official docs)", "https://www.postgresql.org/docs/current/tutorial.html", ["data"], "Foundation", "SQL and PostgreSQL essentials."),
]


def course_content(code, title, desc):
    return f"# {title}\n\n**Course code:** {code}  \n**Provider:** Rimal Academy (internal)\n\n{desc}\n\n## Modules\n1. Introduction and objectives\n2. Core concepts with Rimal project examples\n3. Practical walkthrough\n4. Knowledge check\n\n_This is a fictional internal course created for the demo._"


def migrate() -> None:
    """Adds columns introduced after a database was created (SQLite create_all doesn't alter tables)."""
    from sqlalchemy import text
    with engine.begin() as c:
        cols = {r[1] for r in c.execute(text("PRAGMA table_info(users)"))}
        if "temp_hashes_json" not in cols:
            c.execute(text("ALTER TABLE users ADD COLUMN temp_hashes_json TEXT DEFAULT '[]'"))
        cols = {r[1] for r in c.execute(text("PRAGMA table_info(onboarding_cases)"))}
        for col in ("plan_json", "plan_source"):
            if col not in cols:
                c.execute(text(f"ALTER TABLE onboarding_cases ADD COLUMN {col} TEXT DEFAULT ''"))
        for col, typ in (("completed_at", "DATETIME"), ("graduated_at", "DATETIME"), ("completion_seen", "BOOLEAN DEFAULT 0")):
            if col not in cols:
                c.execute(text(f"ALTER TABLE onboarding_cases ADD COLUMN {col} {typ}"))


def run(reset: bool = False) -> None:
    if reset:
        Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    migrate()
    db = SessionLocal()
    if db.query(Department).count():
        from . import seed_extra
        seed_extra.ensure(db)  # extend an existing database without wiping data
        db.close()
        return
    depts = {}
    for name, mission in DEPARTMENTS.items():
        depts[name] = Department(name=name, mission=mission)
        db.add(depts[name])
    db.flush()
    roles = {}
    for r in ROLES:
        roles[r["title"]] = Role(title=r["title"], department_id=depts[r["dept"]].id, summary=r["summary"],
                                 skills_json=J(r["skills"]), responsibilities_json=J(r["responsibilities"]),
                                 equipment_json=J(r["equipment"]), work_example_json=J(r["example"]))
        db.add(roles[r["title"]])
    projects = {}
    for p in PROJECTS:
        projects[p["code"]] = Project(code=p["code"], name=p["name"], client=p["client"], background=p["background"], phase=p["phase"],
                                      objectives_json=J(p["objectives"]), deliverables_json=J(p["deliverables"]))
        db.add(projects[p["code"]])
    db.flush()
    people = {}
    for code, name, email, title, role, dept, mgr, proj in PEOPLE:
        e = Employee(employee_code=code, full_name=name, email=email, title=title,
                     role_id=roles[role].id if role else None, department_id=depts[dept].id,
                     manager_id=people[mgr].id if mgr else None, project_id=projects[proj].id if proj else None,
                     start_date=date(2021, 3, 1), bio=BIOS.get(code, ""))
        db.add(e)
        db.flush()
        people[code] = e
    for proj, sender, rcpt, subj, at, body in EMAILS:
        db.add(CompanyEmail(project_id=projects[proj].id if proj else None, sender=sender, recipients=rcpt, subject=subj, body=body, sent_at=d(at)))
    for proj, kind, title, body in DOCS:
        db.add(CompanyDocument(project_id=projects[proj].id if proj else None, kind=kind, title=title, body=body))
    for code, title, skills, level, hours, mand, desc in COURSES:
        db.add(Course(code=code, title=title, description=desc, skills_json=J(skills), level=level, hours=hours, mandatory=mand,
                      content_md=course_content(code, title, desc)))
    for code, title, provider, url, skills, level, desc in EXTERNAL:
        db.add(Course(code=code, title=title, provider=provider, url=url, external=True, description=desc, skills_json=J(skills),
                      level=level, hours=0, mandatory=False))
    # HR account (demo credentials documented in README only)
    # On a server set HR_PASSWORD (secret); the demo password is only for local use.
    import os
    db.add(User(username="hr@rimal.example", password_hash=hash_password(os.environ.get("HR_PASSWORD") or "Rimal-HR-2026!"),
                kind="hr", employee_id=people["R-0010"].id))
    db.commit()
    from . import seed_extra
    seed_extra.ensure(db)
    db.close()


if __name__ == "__main__":
    import sys
    run(reset="--reset" in sys.argv)
    print("Database seeded.")
