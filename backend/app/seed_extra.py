"""Additional job roles, staff and courses. Applied idempotently on every startup, so it extends an existing
database without wiping employees that HR has already added. External URLs were checked to load (HTTP 200)."""
from datetime import date

from .models import Course, Department, Employee, Role, JSONMixin

J = JSONMixin.dump
SK = lambda key, name, kws: {"key": key, "name": name, "keywords": kws}
EQ = lambda item, kind, reason: {"item": item, "kind": kind, "reason": reason}
R = lambda title, detail, skills: {"title": title, "detail": detail, "skills": skills}

DEPARTMENTS = {"Health, Safety & Environment": "Keeps every Rimal site safe: permits, inspections, training and incident prevention."}

ROLES = [
    dict(title="Procurement Specialist", dept="Procurement",
         summary="Sources, evaluates and buys the equipment and materials our projects need, on time and within budget.",
         skills=[SK("sourcing", "Supplier sourcing & RFQs", ["sourcing", "supplier", "vendor", "rfq", "tender", "quotation"]),
                 SK("contracts", "Contracts & purchase orders", ["contract", "negotiat", "purchase order", " po ", "incoterms"]),
                 SK("erp", "ERP purchasing (SAP / Oracle)", ["sap", "oracle", "erp", "ariba"]),
                 SK("expedite", "Expediting & logistics", ["expedit", "logistics", "delivery", "shipping", "lead time"]),
                 SK("tech", "Reading electrical specifications", ["switchgear", "cable", "transformer", "technical specification", "datasheet", "electrical"])],
         responsibilities=[R("Run RFQs and compare vendor quotations", "Issue RFQs, collect bids and build the comparison sheet.", ["sourcing", "tech"]),
                           R("Raise purchase orders in SAP", "Create POs with correct terms once the evaluation is approved.", ["erp", "contracts"]),
                           R("Expedite long-lead equipment", "Track switchgear and cable deliveries against the project schedule.", ["expedite"]),
                           R("Support technical-commercial evaluations", "Work with engineers to score vendors on price and compliance.", ["tech", "sourcing"])],
         equipment=[EQ("Standard laptop (16 GB)", "hardware", "Office, ERP and evaluation spreadsheets."),
                    EQ("SAP purchasing account", "access", "All purchase orders are raised in SAP."),
                    EQ("Aconex account", "access", "Vendor documents and technical submittals."),
                    EQ("Microsoft 365 licence", "software", "Email, Excel and Teams with suppliers.")],
         example={"title": "Compare three switchgear quotations",
                  "scenario": "The Metro Depot team needs 33 kV switchgear. Three vendors have quoted, and the PM needs a recommendation by Thursday.",
                  "steps": ["Collect the three quotations and datasheets", "Check each against the technical specification", "Normalise prices and delivery times", "Flag commercial risks and exclusions", "Send a one-page recommendation to the PM"],
                  "deliverable": "A comparison sheet and a short recommendation note."}),
    dict(title="HR Specialist", dept="Human Resources",
         summary="Supports recruitment, onboarding, employee records and payroll inputs across Rimal.",
         skills=[SK("recruit", "Recruitment & interviewing", ["recruit", "talent", "interview", "hiring", "candidate"]),
                 SK("onboard", "Onboarding & induction", ["onboarding", "induction", "orientation", "new joiner"]),
                 SK("payroll", "Payroll, GOSI & benefits", ["payroll", "gosi", "compensation", "benefits", "insurance"]),
                 SK("labor", "Saudi labor law & HR policy", ["labor law", "labour law", "saudi labor", "compliance", "hr policy"]),
                 SK("hris", "HR systems (HRIS)", ["hris", "successfactors", "workday", "oracle hcm", "excel"])],
         responsibilities=[R("Coordinate new-joiner onboarding", "Make sure paperwork, equipment and first-week plans are ready.", ["onboard"]),
                           R("Manage the recruitment pipeline", "Schedule interviews and keep candidates informed.", ["recruit"]),
                           R("Maintain employee records in the HRIS", "Keep contracts, IDs and changes accurate.", ["hris", "labor"]),
                           R("Prepare monthly payroll & GOSI inputs", "Collect changes and check them before payroll closes.", ["payroll"])],
         equipment=[EQ("Standard laptop (16 GB)", "hardware", "HR systems and documents."),
                    EQ("HRIS access", "access", "Employee records and approvals."),
                    EQ("Tamheed HR workspace access", "access", "Onboarding preparation and tracking."),
                    EQ("Microsoft 365 licence", "software", "Email, Teams and documents.")],
         example={"title": "Prepare onboarding for an engineer starting Sunday",
                  "scenario": "A new electrical engineer starts Sunday on the Al Noor project. Make sure day one goes smoothly.",
                  "steps": ["Add the employee and CV in Tamheed", "Confirm the laptop and site PPE with IT", "Book the 1:1 with the manager", "Check the contract and ID are on file", "Send the welcome invitation"],
                  "deliverable": "A ready workspace and a confirmed day-one schedule."}),
    dict(title="Data Analyst", dept="Digital & Software",
         summary="Turns energy and project data into dashboards and insights for our clients and project teams.",
         skills=[SK("sql", "SQL & databases", ["sql", "postgres", "mysql", "database", "query"]),
                 SK("bi", "Dashboards (Power BI / Tableau)", ["power bi", "tableau", "dashboard", "visuali", "looker"]),
                 SK("python", "Python for data (pandas)", ["python", "pandas", "numpy", "jupyter"]),
                 SK("stats", "Statistics & analysis", ["statistic", "regression", "forecast", "analysis", "analytics"]),
                 SK("energy", "Energy & building data", ["energy", "hvac", "bms", "kwh", "consumption"])],
         responsibilities=[R("Build the King Fahd Tower energy baseline", "Establish the pre-retrofit energy baseline per floor.", ["energy", "stats"]),
                           R("Maintain client Power BI dashboards", "Keep energy and alarm dashboards accurate and fast.", ["bi", "sql"]),
                           R("Automate data cleaning", "Script the cleanup of meter and BMS exports.", ["python"]),
                           R("Explain findings to project teams", "Turn analysis into clear recommendations.", ["stats"])],
         equipment=[EQ("Laptop (32 GB RAM)", "hardware", "Large datasets and Power BI Desktop."),
                    EQ("Power BI Pro licence", "software", "Publishing client dashboards."),
                    EQ("Read access to the telemetry database", "access", "Source data for analysis."),
                    EQ("VPN certificate", "access", "Reach the KFT data platform.")],
         example={"title": "Find why floor 30 energy rose 12%",
                  "scenario": "Facilities reports that floor 30 used 12% more energy last month. Find out why.",
                  "steps": ["Pull floor 30 meter data for three months", "Compare against occupancy and weather", "Check AHU run hours in the BMS data", "Identify the abnormal pattern", "Share a one-page finding"],
                  "deliverable": "A short finding with a chart and a recommended action."}),
    dict(title="HSE Officer", dept="Health, Safety & Environment",
         summary="Keeps our substation and building sites safe through permits, inspections, training and incident prevention.",
         skills=[SK("hse", "HSE management", ["hse", "osha", "nebosh", "iosh", "safety officer", "safety"]),
                 SK("ptw", "Permit to work & LOTO", ["permit to work", "ptw", "loto", "lock-out", "isolation"]),
                 SK("risk", "Risk assessment", ["risk assessment", "hazard", "hira", "jsa", "method statement"]),
                 SK("audit", "Inspections & incident investigation", ["audit", "inspection", "incident", "root cause"]),
                 SK("training", "Safety training & toolbox talks", ["toolbox", "induction", "training"])],
         responsibilities=[R("Run daily site safety walks", "Inspect work areas and close out unsafe conditions.", ["audit", "hse"]),
                           R("Review permits to work for energised areas", "Check isolations and LOTO before work starts.", ["ptw"]),
                           R("Deliver toolbox talks", "Short daily safety briefings for site crews.", ["training"]),
                           R("Investigate near misses", "Find root causes and track corrective actions.", ["audit", "risk"])],
         equipment=[EQ("Site PPE kit (helmet, FR coveralls, boots, gloves)", "hardware", "Daily site presence."),
                    EQ("Multi-gas detector", "hardware", "Confined-space and cable-trench checks."),
                    EQ("Site access card", "access", "Entry to client substations."),
                    EQ("Tablet with HSE inspection app", "software", "Record inspections and photos on site.")],
         example={"title": "Review a permit to work for Bay 3 relay testing",
                  "scenario": "The testing team wants to start secondary injection on Bay 3 tomorrow morning. Review their permit.",
                  "steps": ["Check the isolation points listed", "Confirm LOTO locks and tags", "Verify the method statement and risk assessment", "Brief the crew in a toolbox talk", "Sign or return the permit with comments"],
                  "deliverable": "An approved permit, or a list of corrections."}),
    dict(title="Protection & Testing Engineer", dept="Electrical Engineering",
         summary="Sets, tests and commissions the protection and automation systems in our substations.",
         skills=[SK("protection", "Protection relays & settings", ["protection", "relay", "differential", "distance", "overcurrent"]),
                 SK("testing", "Testing & commissioning", ["testing", "commissioning", "omicron", "secondary injection", " fat", " sat"]),
                 SK("iec", "IEC 61850 & substation automation", ["iec 61850", "scada", "substation automation", "goose"]),
                 SK("power", "Substation equipment", ["substation", "switchgear", "transformer", "kv"]),
                 SK("docs", "Test reports & ITPs", ["test report", "itp", "documentation"])],
         responsibilities=[R("Review relay settings", "Check settings against the client's protection philosophy.", ["protection"]),
                           R("Perform secondary injection tests", "Test relays and record results on site.", ["testing", "protection"]),
                           R("Configure IEC 61850 / SCADA mapping", "Work with Digital on point lists and GOOSE messages.", ["iec"]),
                           R("Write commissioning test reports", "Clear, signed reports for client approval.", ["docs", "testing"])],
         equipment=[EQ("Engineering laptop (32 GB RAM)", "hardware", "Relay software and test files."),
                    EQ("OMICRON test set booking access", "access", "Secondary injection testing."),
                    EQ("Relay configuration software licences", "software", "Settings and IEC 61850 configuration."),
                    EQ("Site PPE kit (arc-rated)", "hardware", "Work in energised substations.")],
         example={"title": "Verify the Bay 3 differential relay settings",
                  "scenario": "Before the factory acceptance test, check that the Bay 3 transformer differential slope settings follow PP-04.",
                  "steps": ["Open the settings file and PP-04", "Compare slope and pickup values", "Simulate an internal and external fault", "Note any deviations", "Send results to Omar for review"],
                  "deliverable": "A checked settings sheet with any deviations explained."}),
    dict(title="Document Controller", dept="Project Management Office",
         summary="Keeps every project drawing, submittal and transmittal current, so inspections never fail on paperwork.",
         skills=[SK("docs", "Document control", ["document control", "document register", "submittal", "transmittal"]),
                 SK("edms", "EDMS (Aconex / SharePoint)", ["aconex", "sharepoint", "edms", "procore"]),
                 SK("revision", "Revision & version control", ["revision", "version control", "as-built"]),
                 SK("comm", "Coordination with clients & engineers", ["client", "coordinat", "communication"]),
                 SK("excel", "Trackers & reporting (Excel)", ["excel", "report", "tracker"])],
         responsibilities=[R("Maintain the project document register", "Every drawing and revision, always current.", ["docs", "revision"]),
                           R("Issue transmittals through Aconex", "Send and log documents to the client.", ["edms"]),
                           R("Run the 48-hour pre-inspection register check", "Procedure PROC-NSU-07.", ["docs", "revision"]),
                           R("Send the weekly document status report", "Open submittals, overdue reviews and RFIs.", ["excel", "comm"])],
         equipment=[EQ("Standard laptop (16 GB)", "hardware", "Registers and Aconex."),
                    EQ("Aconex account", "access", "All client transmittals."),
                    EQ("SharePoint project site access", "access", "Internal document library."),
                    EQ("Scanner & large-format printer access", "hardware", "Site copies of current revisions.")],
         example={"title": "Pre-inspection register check for Feeder Bay 3",
                  "scenario": "The client inspects Feeder Bay 3 on Thursday. Make sure every document on site is the latest approved revision.",
                  "steps": ["Export the register for Feeder Bay 3", "Compare revisions with approved submittals", "Replace outdated site copies", "Confirm the ITP is signed", "Send the readiness note to the PM"],
                  "deliverable": "A readiness note listing any gaps and owners."}),
    dict(title="IT Support Engineer", dept="Digital & Software",
         summary="Keeps Rimal's people productive and secure: laptops, accounts, network and the service desk.",
         skills=[SK("support", "Service desk & troubleshooting", ["help desk", "service desk", "it support", "troubleshoot", "ticket"]),
                 SK("endpoint", "Endpoint management (Windows / macOS)", ["windows", "macos", "intune", "active directory", "endpoint"]),
                 SK("network", "Networking & VPN", ["network", "vpn", "firewall", "tcp/ip", "wifi"]),
                 SK("security", "Security & MFA", ["mfa", "security", "antivirus", "phishing"]),
                 SK("cloud", "Microsoft 365 administration", ["microsoft 365", "office 365", "azure", "exchange"])],
         responsibilities=[R("Prepare laptops and accounts for new joiners", "Ready before day one, with licences and MFA.", ["endpoint", "cloud"]),
                           R("Resolve service desk tickets", "Fix issues and keep users informed.", ["support"]),
                           R("Manage MFA and VPN access", "Enrol users and keep remote access secure.", ["security", "network"]),
                           R("Keep the IT asset inventory current", "Track every laptop, licence and device.", ["support"])],
         equipment=[EQ("Laptop with admin tools", "hardware", "Support and device management."),
                    EQ("Admin accounts (Intune, Microsoft 365)", "access", "Manage devices and users."),
                    EQ("IT toolkit and spare peripherals", "hardware", "Desk-side support."),
                    EQ("Service desk system access", "software", "Ticket handling.")],
         example={"title": "Set up a new engineer before day one",
                  "scenario": "A new electrical engineer starts Sunday. They need a workstation laptop, AutoCAD, Aconex and MFA ready.",
                  "steps": ["Image the laptop and enrol it in Intune", "Create the Microsoft 365 account", "Assign AutoCAD and Aconex licences", "Prepare the MFA enrolment", "Mark the equipment tasks ready in Tamheed"],
                  "deliverable": "A working laptop and accounts, handed over on day one."}),
]

COURSES = [  # (code, title, skills, level, hours, description)
    ("PROC-101", "Procurement at Rimal: RFQs, Evaluations & POs", ["sourcing", "contracts", "erp"], "Foundation", 4.0, "Our end-to-end purchasing process, from RFQ to purchase order in SAP."),
    ("PROC-110", "Expediting Long-Lead Electrical Equipment", ["expedite", "tech"], "Intermediate", 3.0, "Tracking switchgear, transformers and cable from factory to site."),
    ("HR-101", "HR Operations at Rimal: Onboarding, Records & Payroll", ["onboard", "hris", "payroll"], "Foundation", 4.0, "How HR runs onboarding, records and payroll inputs at Rimal."),
    ("HR-110", "Saudi Labor Law Essentials for HR", ["labor"], "Intermediate", 3.0, "Contracts, working hours, leave and end-of-service rules."),
    ("DATA-101", "Energy Data Analytics with SQL & Power BI", ["sql", "bi", "energy"], "Intermediate", 6.0, "Our energy datasets, models and dashboard standards."),
    ("DATA-110", "Python for Data Analysis", ["python", "stats"], "Foundation", 6.0, "pandas, cleaning and analysis on real meter data."),
    ("HSE-101", "Permit to Work, LOTO & Energised Areas", ["ptw", "hse"], "Intermediate", 4.0, "Rimal's permit system and isolation rules for substations."),
    ("HSE-110", "Incident Investigation & Toolbox Talks", ["audit", "training", "risk"], "Intermediate", 3.0, "Root-cause analysis and running effective safety briefings."),
    ("ENG-140", "Secondary Injection Testing in Practice", ["testing", "protection"], "Intermediate", 5.0, "Test set-up, relay testing and recording results."),
    ("DOC-101", "Aconex & Transmittals Masterclass", ["edms", "revision", "docs"], "Foundation", 3.0, "Registers, transmittals and revision control the Rimal way."),
    ("IT-101", "Rimal IT Service Desk & Endpoint Management", ["support", "endpoint", "security"], "Foundation", 3.0, "Our tools, ticket process and device standards."),
    ("IT-110", "Networking & VPN Basics", ["network"], "Foundation", 3.0, "How our offices, sites and VPN connect."),
]

EXTERNAL = [  # (code, title, provider, url, skills, level, description)
    ("EXT-PBI", "Power BI training", "Microsoft Learn", "https://learn.microsoft.com/en-us/training/powerplatform/power-bi", ["bi", "sql"], "Foundation", "Free official learning paths for Power BI."),
    ("EXT-GDA", "Google Data Analytics Professional Certificate", "Google via Coursera", "https://www.coursera.org/professional-certificates/google-data-analytics", ["stats", "sql", "bi"], "Foundation", "Data cleaning, analysis and visualisation."),
    ("EXT-GIT", "Google IT Support Professional Certificate", "Google via Coursera", "https://www.coursera.org/professional-certificates/google-it-support", ["support", "network", "endpoint", "security"], "Foundation", "Troubleshooting, networking, systems and security."),
    ("EXT-NEB", "NEBOSH health & safety qualifications", "NEBOSH", "https://www.nebosh.org.uk/", ["hse", "risk", "audit"], "Intermediate", "Internationally recognised HSE qualifications."),
    ("EXT-IOSH", "IOSH safety training", "IOSH", "https://www.iosh.com/", ["hse", "training"], "Foundation", "Safety training for managers and supervisors."),
    ("EXT-CIPS", "CIPS procurement qualifications", "CIPS", "https://www.cips.org/", ["sourcing", "contracts"], "Intermediate", "Professional procurement and supply qualifications."),
    ("EXT-SCM", "Supply Chain Management Specialization", "Rutgers via Coursera", "https://www.coursera.org/specializations/supply-chain-management", ["expedite", "sourcing"], "Foundation", "Logistics, sourcing and supply chain planning."),
    ("EXT-HRM", "Human Resource Management Specialization", "University of Minnesota via Coursera", "https://www.coursera.org/specializations/human-resource-management", ["recruit", "onboard", "payroll", "labor"], "Foundation", "Recruiting, performance, compensation and HR practice."),
    ("EXT-MSL", "Microsoft Learn: Microsoft 365 & Azure", "Microsoft Learn", "https://learn.microsoft.com/en-us/training/", ["cloud", "security"], "Foundation", "Official Microsoft training paths."),
]

# (code, name, email, title, role, dept, manager_code, project_code, bio)
PEOPLE = [
    ("R-0070", "Mona Al-Dossari", "mona.aldossari@rimal.example", "HSE Manager", "HSE Officer", "Health, Safety & Environment", "R-0001", "NSU",
     "Leads site safety across all projects; approves permits for energised areas."),
    ("R-0043", "Rawan Al-Shammari", "rawan.alshammari@rimal.example", "Data Analyst", "Data Analyst", "Digital & Software", "R-0040", "KFT",
     "Builds the KFT energy dashboards and baseline reports."),
    ("R-0033", "Huda Al-Ali", "huda.alali@rimal.example", "Senior Document Controller", "Document Controller", "Project Management Office", "R-0031", "NSU",
     "Owns the Al Noor document register and Aconex transmittals."),
]
# Existing staff who now map to the new roles (so new hires get a real mentor).
ROLE_FOR_EXISTING = {"R-0050": "Procurement Specialist", "R-0060": "IT Support Engineer", "R-0023": "Protection & Testing Engineer", "R-0010": "HR Specialist"}


def ensure(db) -> None:
    from .seed import course_content
    depts = {d.name: d for d in db.query(Department)}
    for name, mission in DEPARTMENTS.items():
        if name not in depts:
            depts[name] = Department(name=name, mission=mission)
            db.add(depts[name])
    db.flush()
    roles = {r.title: r for r in db.query(Role)}
    for r in ROLES:
        if r["title"] not in roles:
            roles[r["title"]] = Role(title=r["title"], department_id=depts[r["dept"]].id, summary=r["summary"], skills_json=J(r["skills"]),
                                     responsibilities_json=J(r["responsibilities"]), equipment_json=J(r["equipment"]), work_example_json=J(r["example"]))
            db.add(roles[r["title"]])
    db.flush()
    codes = {c for (c,) in db.query(Course.code)}
    for code, title, skills, level, hours, desc in COURSES:
        if code not in codes:
            db.add(Course(code=code, title=title, description=desc, skills_json=J(skills), level=level, hours=hours, content_md=course_content(code, title, desc)))
    for code, title, provider, url, skills, level, desc in EXTERNAL:
        if code not in codes:
            db.add(Course(code=code, title=title, provider=provider, url=url, external=True, description=desc, skills_json=J(skills), level=level, hours=0))
    staff = {e.employee_code: e for e in db.query(Employee)}
    projects = {p.code: p.id for p in db.query(__import__("app.models", fromlist=["Project"]).Project)}
    for code, name, email, title, role, dept, mgr, proj, bio in PEOPLE:
        if code not in staff and mgr in staff:
            db.add(Employee(employee_code=code, full_name=name, email=email, title=title, role_id=roles[role].id, department_id=depts[dept].id,
                            manager_id=staff[mgr].id, project_id=projects.get(proj), start_date=date(2022, 1, 9), bio=bio))
    for code, role in ROLE_FOR_EXISTING.items():
        if code in staff and (staff[code].role_id is None or staff[code].title == role):
            staff[code].role_id = roles[role].id
    db.commit()
    ensure_knowledge(db)


# ================================================================= richer company knowledge (projects, clients, emails, documents)
PROJECTS = [
    dict(code="JSP", name="Jubail 300 MW Solar PV Grid Connection", client="SunEast Renewables (fictional)", phase="Tendering & early design",
         background="Rimal is bidding to design and build the 380/33 kV collector substation and grid connection for a 300 MW solar PV plant near Jubail.",
         objectives=["Submit a compliant technical bid by 15 December 2026", "Complete the grid-code compliance study", "Win the EPC contract"],
         deliverables=["Technical proposal", "Grid-code compliance study", "Preliminary single-line diagram", "Bid price and schedule"]),
    dict(code="RDC", name="Riyadh Data Centre Power Upgrade", client="NovaCloud Arabia (fictional)", phase="Construction",
         background="Upgrade of a live Tier III data centre from 8 MW to 14 MW IT load, adding a new 13.8 kV switchboard, two 2.5 MVA UPS systems and generators — without any downtime.",
         objectives=["Zero unplanned outages during cut-overs", "Commission the new switchboard by February 2027", "Pass the Uptime Institute re-certification"],
         deliverables=["Cut-over method statements", "Integrated systems test (IST) plan", "UPS and generator commissioning records"]),
]

PEOPLE_MORE = [
    ("R-0034", "Salman Al-Rasheed", "salman.alrasheed@rimal.example", "Project Manager — Data Centre", "Project Coordinator", "Project Management Office", "R-0030", "RDC",
     "Runs the NovaCloud data-centre upgrade; very strict about live-site rules."),
    ("R-0024", "Nadia Farouk", "nadia.farouk@rimal.example", "Senior Electrical Engineer — Renewables", "Electrical Project Engineer", "Electrical Engineering", "R-0020", "JSP",
     "Leads the Jubail solar bid's electrical design and grid-code study."),
    ("R-0025", "Fahad Al-Subaie", "fahad.alsubaie@rimal.example", "Electrical Engineer — Critical Power", "Electrical Project Engineer", "Electrical Engineering", "R-0020", "RDC",
     "UPS, generators and switchboard cut-overs on the data-centre project."),
    ("R-0051", "Layla Al-Mansour", "layla.almansour@rimal.example", "Commercial & Bids Manager", None, "Procurement", "R-0001", "JSP",
     "Owns bid pricing, commercial risk and client contracts."),
]

D = lambda y, m, d, h=9, mi=0: f"{y}-{m:02d}-{d:02d}T{h:02d}:{mi:02d}"
EMAILS_MORE = [  # (project, sender, recipients, subject, sent_at, body)
    ("NSU", "yousef.nasser@rimal.example", "Al Noor project team", "Minutes: weekly coordination meeting — 26 Oct", D(2026, 10, 26, 10),
     "Attendees: Yousef, Khalid, Omar, Lina, Huda, Mona.\n\n1. Bay 3 cable pulling 85% complete; remaining 15% blocked by the trench crossing near the control building — civil subcontractor to finish by 2 Nov.\n2. Bay 4 GIS delivery confirmed for 18 Nov.\n3. HSE: one near miss (unbarricaded trench) — Mona issued a stand-down; barricading now checked daily.\n4. Client asked for weekly photos in a single PDF, not separate files.\n\nActions: Lina — update the document register for the Bay 4 GIS drawings; Omar — confirm FAT travel; Huda — issue transmittal for ITP-NSU-14."),
    ("NSU", "mona.aldossari@rimal.example", "Al Noor project team; Khalid Al-Mutairi", "Near miss: unbarricaded cable trench", D(2026, 10, 24, 14, 15),
     "A technician nearly stepped into an open cable trench near Bay 3 at dusk. No injury. Root cause: barricade removed for cable pulling and not replaced at shift end.\n\nCorrective actions: end-of-shift barricade check added to the daily checklist; lighting added at the trench crossing. Please remind your crews in tomorrow's toolbox talk."),
    ("NSU", "khalid.almutairi@rimal.example", "Yousef Nasser; Layla Al-Mansour", "Variation order VO-07: extra feeder for the industrial zone", D(2026, 10, 12, 11),
     "The client has requested one additional 33 kV outgoing feeder for the new industrial zone. Estimated value SAR 1.9M and 4 weeks added to Bay 4. Layla — please prepare the commercial proposal; we must not start work until the VO is approved in writing."),
    ("MDP", "dana.alghamdi@rimal.example", "Metro Depot team", "Client comments on the load-flow study — revision B", D(2026, 10, 22, 13),
     "City Transit Authority returned 14 comments on the load-flow study. The main ones: (1) model the two new 350 kW EV charging feeders, (2) show N-1 contingency for the transformer pair, (3) use their updated 2030 load forecast. Tariq to issue revision C by 6 November."),
    ("MDP", "majed.alotaibi@rimal.example", "Dana Al-Ghamdi; Tariq Al-Shehri", "Vendor Y purchase order issued", D(2026, 10, 9, 10, 30),
     "PO-MDP-0112 for the 33 kV switchgear has been issued to Vendor Y following the technical evaluation. Ex-works delivery: 22 weeks. Payment terms: 10% advance, 80% on delivery, 10% after commissioning."),
    ("KFT", "rawan.alshammari@rimal.example", "Hassan Ali; Sara Mansour", "Energy baseline: first results", D(2026, 10, 19, 15),
     "Baseline for floors 1–25 is complete: 4.1 GWh/year, of which HVAC is 58%. Floors 18–20 use 22% more than similar floors — likely AHU schedules running on weekends. I'll confirm with the BMS run-hour data this week."),
    ("KFT", "hassan.ali@rimal.example", "Tower Facilities Co. (client)", "December change freeze — impact on our schedule", D(2026, 10, 27, 9, 30),
     "Thank you for confirming your IT change freeze from 10 to 31 December. We will complete the router installation and floors 26–42 migration before 9 December, and schedule only read-only monitoring work during the freeze."),
    ("JSP", "layla.almansour@rimal.example", "Jubail bid team", "Bid kick-off: Jubail 300 MW solar grid connection", D(2026, 10, 5, 9),
     "We have received the tender from SunEast Renewables. Submission deadline: 15 December 2026. Evaluation is 60% technical, 40% commercial. Nadia leads technical, I lead commercial, Majed supports with transformer and switchgear quotes. Bid/no-bid review on 12 October."),
    ("JSP", "faisal.alharbi@rimal.example", "Jubail bid team", "Decision: we will bid for Jubail", D(2026, 10, 12, 16),
     "After the bid/no-bid review we will bid. Reasons: renewables is a strategic growth area, our substation experience on Al Noor is directly relevant, and the client's payment history is strong. Risk: tight schedule — we must not compromise Al Noor resources."),
    ("JSP", "nadia.farouk@rimal.example", "Layla Al-Mansour; Khalid Al-Mutairi", "Grid-code study: reactive power requirement", D(2026, 10, 25, 12),
     "The grid code requires the plant to provide reactive power at 0.95 power factor at the point of connection. Our preliminary study shows the inverters alone cannot meet this at full output, so we recommend a 40 MVAr STATCOM. This adds roughly SAR 9M to the bid — Layla, please include it as a separate line item."),
    ("RDC", "salman.alrasheed@rimal.example", "Data centre project team", "Live-site rules — please read before your first visit", D(2026, 9, 7, 8),
     "NovaCloud is a live Tier III data centre. Rules: (1) no work on any live system without an approved method of procedure (MOP) signed by NovaCloud; (2) cut-overs only in the agreed maintenance window, Friday 01:00–05:00; (3) escort required in white space; (4) no photos inside data halls. Breaking these rules can stop the project."),
    ("RDC", "fahad.alsubaie@rimal.example", "Salman Al-Rasheed; Omar Haddad", "UPS-2 factory test passed", D(2026, 10, 16, 17),
     "UPS-2 passed its factory acceptance test, including the 100% step-load and battery autonomy tests (11.5 minutes at full load, spec is 10). Delivery to site on 3 November."),
    ("RDC", "salman.alrasheed@rimal.example", "NovaCloud Arabia (client)", "Cut-over 2 postponed by one week", D(2026, 10, 23, 18),
     "As discussed, cut-over 2 (transfer of PDU-B to the new switchboard) moves from 31 October to 7 November because the generator load-bank test showed a governor fault on GEN-3. The vendor replaces the governor on 4 November and we re-test on 5 November. No change to the February completion date."),
    (None, "noura.alqahtani@rimal.example", "All staff", "Ramadan and Eid working hours", D(2026, 9, 20, 9),
     "During Ramadan, office hours are 9:00–15:00 Sunday–Thursday. Site hours follow the client's rules. Eid holidays will be announced by HR once the official dates are confirmed."),
    (None, "faisal.alharbi@rimal.example", "All staff", "Q3 results and thank you", D(2026, 10, 8, 9),
     "Q3 was our best quarter: revenue up 18%, Al Noor on schedule, Metro Depot vendor selected, and King Fahd Tower ahead of plan. We also started the Jubail bid and the NovaCloud data centre. Thank you all — and welcome to everyone who joined this quarter."),
    (None, "ibrahim.saleh@rimal.example", "All staff", "Phishing alert: fake 'invoice' emails", D(2026, 10, 18, 11),
     "We received several fake invoice emails pretending to be from a supplier. Never open attachments from unexpected invoices — forward them to IT. If you clicked a link, tell IT immediately; you won't get in trouble."),
    (None, "noura.alqahtani@rimal.example", "All new joiners", "Welcome lunch for new joiners", D(2026, 10, 28, 10),
     "New joiners are invited to the monthly welcome lunch with the CEO on the first Tuesday of each month at 13:00 in the 4th-floor meeting room. It's a relaxed chance to meet colleagues from other departments."),
    ("MDP", "tariq.alshehri@rimal.example", "Dana Al-Ghamdi", "Lesson learned: always ask for the client's latest load forecast", D(2026, 10, 23, 9),
     "Revision B of the load-flow study used the 2025 forecast because it was in the tender documents. The client had issued a 2030 forecast in July. Going forward, we confirm the latest planning data with the client before starting any study."),
]

DOCS_MORE = [  # (project, kind, title, body)
    (None, "org-chart", "Rimal organisation chart",
     "CEO: Faisal Al-Harbi. Head of Electrical Engineering: Khalid Al-Mutairi (Omar Haddad, Lina Saeed, Tariq Al-Shehri, Nadia Farouk, Fahad Al-Subaie). Head of PMO: Reem Al-Zahrani (Yousef Nasser — Al Noor, Dana Al-Ghamdi — Metro Depot, Salman Al-Rasheed — Data Centre, Huda Al-Ali — Document Control). Head of Digital & Software: Hassan Ali (Sara Mansour, Ahmed Karim, Rawan Al-Shammari, Ibrahim Saleh — IT). Procurement: Majed Al-Otaibi; Commercial & Bids: Layla Al-Mansour. HR: Noura Al-Qahtani. HSE: Mona Al-Dossari."),
    (None, "policy", "New joiner FAQ",
     "Office: Rimal Tower, King Fahd Road, Riyadh, floors 3–5. Hours: Sunday–Thursday 8:00–17:00. Parking: basement B2 with your access card (issued by HR on day one). Cafeteria: 3rd floor, 7:30–15:00. Prayer rooms on every floor. Laptop and accounts: IT service desk (Ibrahim Saleh). Questions about pay, leave or insurance: HR (Noura Al-Qahtani). Site visits require the HSE induction first."),
    (None, "policy", "Leave, travel and expenses policy",
     "Annual leave: 30 days per year after probation; request in the HR portal at least 2 weeks ahead. Sick leave needs a medical note after 1 day. Business travel: book through HR travel desk; economy class under 6 hours. Per diem SAR 400/day inside KSA. Expense claims within 30 days with receipts; manager approves, finance pays within 2 weeks."),
    (None, "policy", "Performance and probation",
     "Probation is 90 days. Your manager holds check-ins at 30, 60 and 90 days against goals agreed in your first week. Annual reviews happen in December. Training completion and feedback from your mentor are part of the probation review."),
    (None, "client-profile", "Client profile: Eastern Grid Utility (Al Noor)",
     "Regional transmission utility. Main contact: the Project Director's office; all formal communication through Aconex letters. Very strict on document revisions at inspections. Weekly progress photos every Thursday as one PDF. Payment: monthly progress certificates."),
    (None, "client-profile", "Client profile: City Transit Authority (Metro Depot)",
     "Public transport authority. Reviews are thorough and slow (about 3 weeks per submission). Always confirm the latest planning data and standards before starting a study. Prefers formal review meetings with minutes."),
    (None, "client-profile", "Client profile: Tower Facilities Co. (King Fahd Tower)",
     "Facility manager of a 42-floor office tower. Practical and responsive. IT change freeze each December. Interested in measurable energy savings; monthly energy report expected."),
    (None, "client-profile", "Client profile: NovaCloud Arabia (Data Centre)",
     "Data-centre operator. Uptime is everything: every task on live systems needs an approved method of procedure (MOP); cut-overs only Friday 01:00–05:00. Escorts required in data halls; no photography."),
    (None, "client-profile", "Client profile: SunEast Renewables (Jubail bid)",
     "Solar developer. Tender evaluation 60% technical / 40% commercial. Values grid-code compliance and schedule certainty. Bid deadline 15 December 2026."),
    ("RDC", "charter", "Data Centre Upgrade project charter",
     "Scope: increase IT capacity from 8 to 14 MW at a live Tier III site: new 13.8 kV switchboard, 2 x 2.5 MVA UPS, 2 generators. PM: Salman Al-Rasheed. Engineering: Fahad Al-Subaie. Budget SAR 36M. Completion: February 2027. Key rule: zero unplanned downtime."),
    ("JSP", "charter", "Jubail solar bid plan",
     "Bid for the 380/33 kV collector substation and grid connection of a 300 MW solar PV plant. Technical lead: Nadia Farouk. Commercial lead: Layla Al-Mansour. Deadline 15 December 2026. Key technical risk: reactive power compliance (STATCOM likely required)."),
    ("NSU", "risk-register", "Al Noor risk register (top 5)",
     "R1 Bay 4 GIS delivery delay — medium, mitigated by weekly vendor calls. R2 Inspection rejection from outdated documents — reduced by the 48-hour register check (PROC-NSU-07). R3 Trench safety — near miss in October; daily barricade check. R4 VO-07 approval delay — commercial follow-up by Layla. R5 Cable supplier B delivery — on track after the D-012 switch."),
    ("RDC", "meeting-notes", "Data Centre progress meeting — 23 Oct 2026",
     "UPS-2 passed FAT; delivery 3 November. GEN-3 governor fault found during load-bank test; replacement 4 November, re-test 5 November. Cut-over 2 moved to 7 November. MOP-14 for cut-over 2 approved by NovaCloud. Next IST planning workshop 12 November."),
]


def ensure_knowledge(db) -> None:
    from datetime import datetime
    from .models import CompanyDocument, CompanyEmail, Project
    projects = {p.code: p for p in db.query(Project)}
    for p in PROJECTS:
        if p["code"] not in projects:
            projects[p["code"]] = Project(code=p["code"], name=p["name"], client=p["client"], background=p["background"], phase=p["phase"],
                                          objectives_json=J(p["objectives"]), deliverables_json=J(p["deliverables"]))
            db.add(projects[p["code"]])
    db.flush()
    depts = {d.name: d for d in db.query(Department)}
    roles = {r.title: r for r in db.query(Role)}
    staff = {e.employee_code: e for e in db.query(Employee)}
    for code, name, email, title, role, dept, mgr, proj, bio in PEOPLE_MORE:
        if code not in staff and mgr in staff:
            db.add(Employee(employee_code=code, full_name=name, email=email, title=title, role_id=roles[role].id if role else None,
                            department_id=depts[dept].id, manager_id=staff[mgr].id, project_id=projects[proj].id, start_date=date(2023, 2, 5), bio=bio))
    subjects = {s for (s,) in db.query(CompanyEmail.subject)}
    for proj, sender, rcpt, subj, at, body in EMAILS_MORE:
        if subj not in subjects:
            db.add(CompanyEmail(project_id=projects[proj].id if proj else None, sender=sender, recipients=rcpt, subject=subj, body=body,
                                sent_at=datetime.fromisoformat(at)))
    titles = {t for (t,) in db.query(CompanyDocument.title)}
    for proj, kind, title, body in DOCS_MORE:
        if title not in titles:
            db.add(CompanyDocument(project_id=projects[proj].id if proj else None, kind=kind, title=title, body=body))
    db.commit()
