"""
parse_resume.py
Parses the compiled PDF of Yogeeswar Senagapalli's resume (custom resume.cls).

Verified PDF structure (pdfplumber x_tolerance=2, y_tolerance=2):

  PROFESSIONAL EXPERIENCE
    Oracle, India, Hyderabad Jan 2023 - Present        ← company,location DATE (single space before date)
    Associate Software Developer, Aug 2023 - Present   ← role, DATE
    • bullet (may wrap to next line without bullet)
    Project Intern, Jan 2023 - Jun 2023                ← role without new company header
    • bullet

  EDUCATION
    Masters in Computer Science Sep 2025 - ...         ← degree DATE (single space)
    University of Massachusetts Amherst Amherst, MA    ← institution location (no separator)
    Cumulative Grade Point Average (CGPA): 4.00/4.00

  RESEARCH & PROJECTS   (contains all projects + conference papers, no patents)
    Title | Tech | Link label
    Description highlight line
    • bullet (may wrap)

  PATENT   (separate section, contains only the patent entry)
    Title | Tech | Link label
    Published as a patent with Patent application Number: XXXXXXX
    • bullet (may wrap)

  TECHNICAL SKILLS
    Programming Languages: C, C++, Java, Python (Pytorch, Flask, ...)

  ORGANIZATION & ACTIVITIES
    Company, Location  Role  Date      ← single line, multi-space separated
    • bullet
"""

import json, os, re
import pdfplumber

PDF_PATH    = "resume.pdf"
JSON_PATH   = "resume.json"
STATIC_PATH = "resume_static.json"

SECTION_HEADERS = {
    "experience":   ["professional experience"],
    "education":    ["education"],
    "projects":     ["research & projects"],
    "patents":      ["patent"],
    "skills":       ["technical skills"],
    "activities":   ["organization & activities"],
    "achievements": ["achievements"],
    "about":        ["about"],
}

# Matches a date range at the END of a line (single space before it)
# e.g.  "Jan 2023 - Present"  "Sep 2025 - Expected graduation: May 2027"  "Jul 2019 - Jun 2023"
DATE_END_RE = re.compile(
    r"\s+"
    r"((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{4}"
    r"|Expected graduation[^,\n]*)"
    r"[^\n]*$",
    re.I,
)

BULLET_RE = re.compile(r"^[•\-·*▪]\s*")

# Role keywords to identify a line as a job role
ROLE_RE = re.compile(
    r"\b(developer|intern|engineer|lead|analyst|manager|architect|scientist|researcher|member)\b",
    re.I,
)


# ── Utilities ──────────────────────────────────────────────────────────────────

def extract_text(path: str) -> str:
    pages = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            t = page.extract_text(x_tolerance=2, y_tolerance=2)
            if t: pages.append(t)
    return "\n".join(pages)


def split_sections(text: str) -> dict:
    header_map = {v.lower(): k
                  for k, variants in SECTION_HEADERS.items()
                  for v in variants}
    sections = {k: [] for k in SECTION_HEADERS}
    current  = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line: continue
        norm = line.lower().rstrip(":").strip()
        if norm in header_map and len(line) <= 50:
            current = header_map[norm]
        elif current:
            sections[current].append(line)
    return sections


def parse_name(text: str) -> str:
    for line in text.splitlines():
        s = line.strip()
        if s and not re.fullmatch(r"[•·\s]+", s):
            return s
    return ""


def split_respecting_parens(text: str) -> list:
    items, depth, buf = [], 0, ""
    for ch in text:
        if ch == "(": depth += 1
        elif ch == ")": depth -= 1
        if ch == "," and depth == 0:
            if buf.strip(): items.append(buf.strip())
            buf = ""
        else:
            buf += ch
    if buf.strip(): items.append(buf.strip())
    return items


# ── Skills ─────────────────────────────────────────────────────────────────────

def parse_skills(lines: list) -> dict:
    result = {}
    for line in lines:
        if ":" not in line: continue
        cat, _, rest = line.partition(":")
        cat = cat.strip()
        if len(cat) > 40 or not cat or cat.startswith("•"): continue
        items = split_respecting_parens(rest)
        if items:
            result[cat] = items
    return result


# ── Education ──────────────────────────────────────────────────────────────────

def parse_education(lines: list) -> list:
    """
    Each entry spans 3 lines:
      1. Degree  Date          (has a month/year at end)
      2. Institution  Location (no date; institution name + location concatenated)
      3. CGPA line

    Institution and location are on the same line with no separator.
    We use known institution prefixes to split cleanly, with a regex fallback.
    """
    entries = []
    current = None
    gpa_re  = re.compile(r"(?:cgpa|gpa).*?([\d.]+\s*/\s*[\d.]+)", re.I)

    # Known institution names — add more here if the resume changes.
    # Order longest-first so prefix matching doesn't short-circuit.
    KNOWN_INSTS = [
        "University of Massachusetts Amherst",
        "Anna University, MIT Campus",
        "Massachusetts Institute of Technology",
        "Carnegie Mellon University",
        "Stanford University",
    ]

    def split_inst_loc(line: str):
        """Return (institution, location) from a combined institution+location line."""
        # 1. Try double-space split (safest)
        parts = re.split(r"\s{2,}", line, maxsplit=1)
        if len(parts) == 2:
            return parts[0].strip(), parts[1].strip()
        # 2. Try known institution prefixes
        for inst in KNOWN_INSTS:
            if line.startswith(inst):
                return inst, line[len(inst):].strip()
        # 3. Fallback: split at last comma-containing tail "X, Y"
        m = re.search(r"\s+([A-Z][a-zA-Z]+(?:,\s*[A-Z][a-zA-Z\s]+)+)\s*$", line)
        if m:
            return line[:m.start()].strip(), m.group(1).strip()
        # 4. Give up and use full line as institution
        return line.strip(), ""

    for line in lines:
        gpa_m  = gpa_re.search(line)
        date_m = DATE_END_RE.search(line)

        if gpa_m:
            if current:
                current["gpa"] = gpa_m.group(1).replace(" ", "")

        elif date_m:
            if current:
                entries.append(current)
            degree = line[:date_m.start()].strip()
            date   = date_m.group(0).strip()
            current = {"institution": "", "degree": degree, "location": "",
                       "date": date, "gpa": "", "coursework": ""}

        elif current and not current["institution"]:
            inst, loc = split_inst_loc(line)
            current["institution"] = inst
            current["location"]    = loc

        elif line.lower().startswith("relevant coursework"):
            if current:
                current["coursework"] = line.split(":", 1)[-1].strip()

    if current and current.get("institution"):
        entries.append(current)

    return [e for e in entries if e.get("institution")]


# ── Experience ─────────────────────────────────────────────────────────────────

def parse_experience(lines: list) -> list:
    """
    Company line:  "Oracle, India, Hyderabad Jan 2023 - Present"
                   → LEFT of DATE_END_RE split = "Oracle, India, Hyderabad"
                   → comma-split: company="Oracle", location="India, Hyderabad"
    Role line:     "Associate Software Developer, Aug 2023 - Present"
                   → contains ROLE_RE keyword + date at end
    Bullet:        starts with •
    Continuation:  plain line after a bullet (wraps)
    """
    entries  = []
    cur_co   = None
    cur_role = None

    def flush():
        if cur_role: entries.append(cur_role)

    for line in lines:
        date_m  = DATE_END_RE.search(line)
        is_bullet = BULLET_RE.match(line)

        if date_m and not is_bullet:
            left = line[:date_m.start()].strip()
            date = date_m.group(0).strip()

            if ROLE_RE.search(left):
                # Role line: "Associate Software Developer"
                flush()
                role_name = left.rstrip(",").strip()
                cur_role = {
                    "role":     role_name,
                    "company":  cur_co["company"]  if cur_co else "",
                    "location": cur_co["location"] if cur_co else "",
                    "date":     date,
                    "bullets":  [],
                }
            else:
                # Company line: "Oracle, India, Hyderabad"
                flush()
                cur_role = None
                co_parts = left.split(",", 1)
                cur_co = {
                    "company":  co_parts[0].strip(),
                    "location": co_parts[1].strip() if len(co_parts) > 1 else "",
                    "date":     date,
                }

        elif is_bullet:
            text = BULLET_RE.sub("", line).strip()
            if cur_role:
                cur_role["bullets"].append(text)

        elif cur_role and cur_role["bullets"]:
            # Continuation of previous bullet
            cur_role["bullets"][-1] += " " + line.strip()

    flush()
    return entries


# ── Pipe-entry parser (projects & patents) ────────────────────────────────────

def parse_pipe_entries(lines: list, is_patent: bool = False) -> list:
    """
    Entry header:  Title | Tech | Link label
    Then:          description / patent-number line
                   • bullets (may wrap to plain lines)
    """
    entries  = []
    current  = None

    gh_re     = re.compile(r"github|project code", re.I)
    ieee_re   = re.compile(r"ieee|paper|conference", re.I)
    thesis_re = re.compile(r"thesis", re.I)
    cert_re   = re.compile(r"certificate", re.I)
    number_re = re.compile(
        r"patent\s*(?:application\s*)?(?:number|no\.?)\s*[:\-]?\s*(\d+)", re.I
    )
    bare_num_re = re.compile(r"\b(\d{10,})\b")

    def infer_label(text: str) -> str:
        if gh_re.search(text):     return "GitHub"
        if ieee_re.search(text):   return "Published Paper"
        if thesis_re.search(text): return "Thesis"
        if cert_re.search(text):   return "Certificate"
        return "View"

    def flush():
        if current and current.get("title"):
            entries.append(current)

    for line in lines:
        is_bullet = BULLET_RE.match(line)

        if "|" in line and not is_bullet:
            flush()
            parts = [p.strip() for p in line.split("|")]
            lbl_raw = parts[2] if len(parts) > 2 else ""
            current = {
                "title":        parts[0],
                "technologies": parts[1] if len(parts) > 1 else "",
                "description":  "",
                "link":         "",
                "linkLabel":    infer_label(lbl_raw or (parts[1] if len(parts) > 1 else "")),
            }
            if is_patent:
                current.update({"number": "", "filed": "", "bullets": []})

        elif current and is_bullet:
            text = BULLET_RE.sub("", line).strip()
            if is_patent:
                current["bullets"].append(text)
            else:
                current["description"] = (current["description"] + " " + text).strip()

        elif current:
            num_m  = number_re.search(line)
            bare_m = bare_num_re.search(line)
            if is_patent and num_m:
                current["number"] = num_m.group(1)
            elif is_patent and bare_m and not current.get("number"):
                current["number"] = bare_m.group(1)
            elif is_patent and current.get("bullets"):
                current["bullets"][-1] += " " + line.strip()
            else:
                current["description"] = (current["description"] + " " + line).strip()

    flush()
    return entries


# ── Static loader ──────────────────────────────────────────────────────────────

def load_static() -> dict:
    if os.path.exists(STATIC_PATH):
        with open(STATIC_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {}


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    text     = extract_text(PDF_PATH)
    sections = split_sections(text)
    static   = load_static()

    # Research & Projects section — all projects, no patents
    all_projects = parse_pipe_entries(sections.get("projects", []), is_patent=False)

    # Patent section — dedicated section, parsed with patent mode
    patents = parse_pipe_entries(sections.get("patents", []), is_patent=True)

    # Merge links from resume_static.json — PDF hyperref URLs are not extractable
    project_links = static.get("project_links", {})
    for entry in all_projects:
        match = project_links.get(entry["title"], {})
        if match.get("link"):
            entry["link"]      = match["link"]
            entry["linkLabel"] = match.get("linkLabel", entry.get("linkLabel", "View"))
    for pat in patents:
        match = project_links.get(pat["title"], {})
        if match.get("link"):
            pat["link"]      = match["link"]
            pat["linkLabel"] = match.get("linkLabel", pat.get("linkLabel", "View"))

    resume = {
        "name":           parse_name(text),
        "skills":         parse_skills(sections["skills"]),
        "education":      parse_education(sections["education"]),
        "experience":     parse_experience(sections["experience"]),
        "projects":       all_projects,
        "patents":        patents,
        "tagline":        static.get("tagline", ""),
        "about":          static.get("about", []),
        "certifications": static.get("certifications", []),
    }

    with open(JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(resume, f, indent=2, ensure_ascii=False)

    print(f"Written → {JSON_PATH}")
    print(f"  name:       {resume['name']}")
    print(f"  skills:     {list(resume['skills'].keys())}")
    print(f"  education:  {len(resume['education'])} entries")
    print(f"  experience: {len(resume['experience'])} entries")
    print(f"  projects:   {len(resume['projects'])} entries")
    print(f"  patents:    {len(resume['patents'])} entries")
    for k in ("education", "experience", "projects", "patents"):
        if not resume[k]:
            print(f"  ⚠ WARNING: {k} is empty — check SECTION_HEADERS matches PDF headings")


if __name__ == "__main__":
    main()