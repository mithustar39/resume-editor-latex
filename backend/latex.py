import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from bs4 import BeautifulSoup, NavigableString

LATEX_ESCAPES = {
    "&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#", "_": r"\_",
    "{": r"\{", "}": r"\}", "~": r"\textasciitilde{}", "^": r"\textasciicircum{}",
    "\\": r"\textbackslash{}",
}


def esc(text: str) -> str:
    if not text:
        return ""
    return "".join(LATEX_ESCAPES.get(ch, ch) for ch in str(text))


JAKE_PREAMBLE = r"""
\documentclass[letterpaper,11pt]{article}

\usepackage{latexsym}
\usepackage[empty]{fullpage}
\usepackage{titlesec}
\usepackage{marvosym}
\usepackage[usenames,dvipsnames]{color}
\usepackage{verbatim}
\usepackage{enumitem}
\usepackage[hidelinks]{hyperref}
\usepackage{fancyhdr}
\usepackage[english]{babel}
\usepackage{tabularx}
\pdfgentounicode=1

\pagestyle{fancy}
\fancyhf{}
\fancyfoot{}
\renewcommand{\headrulewidth}{0pt}
\renewcommand{\footrulewidth}{0pt}

\addtolength{\oddsidemargin}{-0.5in}
\addtolength{\evensidemargin}{-0.5in}
\addtolength{\textwidth}{1in}
\addtolength{\topmargin}{-.5in}
\addtolength{\textheight}{1.0in}

\urlstyle{same}
\raggedbottom
\raggedright
\setlength{\tabcolsep}{0in}

\titleformat{\section}{
  \vspace{-4pt}\scshape\raggedright\large
}{}{0em}{}[\color{black}\titlerule \vspace{-5pt}]

\newcommand{\resumeItem}[1]{
  \item\small{
    {#1 \vspace{-2pt}}
  }
}

\newcommand{\resumeSubheading}[4]{
  \vspace{-2pt}\item
    \begin{tabular*}{0.97\textwidth}[t]{l@{\extracolsep{\fill}}r}
      \textbf{#1} & #2 \\
      \textit{\small#3} & \textit{\small #4} \\
    \end{tabular*}\vspace{-7pt}
}

\newcommand{\resumeSubSubheading}[2]{
    \item
    \begin{tabular*}{0.97\textwidth}{l@{\extracolsep{\fill}}r}
      \textit{\small#1} & \textit{\small #2} \\
    \end{tabular*}\vspace{-7pt}
}

\newcommand{\resumeProjectHeading}[2]{
    \item
    \begin{tabular*}{0.97\textwidth}{l@{\extracolsep{\fill}}r}
      \textbf{#1} & #2 \\
    \end{tabular*}\vspace{-7pt}
}

\newcommand{\resumeSubItem}[1]{\resumeItem{#1}\vspace{-4pt}}

\renewcommand\labelitemii{$\vcenter{\hbox{\tiny$\bullet$}}$}

\newcommand{\resumeSubHeadingListStart}{\begin{itemize}[leftmargin=0.15in, label={}]}
\newcommand{\resumeSubHeadingListEnd}{\end{itemize}}
\newcommand{\resumeItemListStart}{\begin{itemize}}
\newcommand{\resumeItemListEnd}{\end{itemize}\vspace{-5pt}}
"""


def render_jake(data: dict) -> str:
    name = esc(data.get("name", "Your Name"))
    parts = []
    if data.get("phone"):
        parts.append(esc(data["phone"]))
    if data.get("email"):
        parts.append(r"\href{mailto:" + data["email"] + "}{\\underline{" + esc(data["email"]) + "}}")
    if data.get("linkedin"):
        parts.append(r"\href{https://" + data["linkedin"] + "}{\\underline{" + esc(data["linkedin"]) + "}}")
    if data.get("github"):
        parts.append(r"\href{https://" + data["github"] + "}{\\underline{" + esc(data["github"]) + "}}")
    if data.get("website"):
        parts.append(r"\href{https://" + data["website"] + "}{\\underline{" + esc(data["website"]) + "}}")
    contact = " $|$ ".join(parts)

    out = [r"\begin{document}", ""]
    out.append(r"\begin{center}")
    out.append(r"    \textbf{\Huge \scshape " + name + r"} \\ \vspace{1pt}")
    out.append(r"    \small " + contact)
    out.append(r"\end{center}")

    if data.get("summary"):
        out.append("\n\\section{Summary}\n" + esc(data["summary"]) + "\n")

    edu = data.get("education") or []
    if edu:
        out.append("\n\\section{Education}")
        out.append(r"\resumeSubHeadingListStart")
        for e in edu:
            out.append("  \\resumeSubheading{" + esc(e.get("school")) + "}{" + esc(e.get("location")) + "}{" +
                       esc(e.get("degree")) + "}{" + esc(e.get("dates")) + "}")
        out.append(r"\resumeSubHeadingListEnd")

    exp = data.get("experience") or []
    if exp:
        out.append("\n\\section{Experience}")
        out.append(r"\resumeSubHeadingListStart")
        for e in exp:
            out.append("  \\resumeSubheading{" + esc(e.get("company")) + "}{" + esc(e.get("location")) + "}{" +
                       esc(e.get("title")) + "}{" + esc(e.get("dates")) + "}")
            bullets = [b for b in (e.get("bullets") or []) if b.strip()]
            if bullets:
                out.append(r"    \resumeItemListStart")
                for b in bullets:
                    out.append(r"      \resumeItem{" + esc(b) + "}")
                out.append(r"    \resumeItemListEnd")
        out.append(r"\resumeSubHeadingListEnd")

    proj = data.get("projects") or []
    if proj:
        out.append("\n\\section{Projects}")
        out.append(r"\resumeSubHeadingListStart")
        for p in proj:
            title = esc(p.get("name"))
            if p.get("tech"):
                title += r" $|$ \emph{" + esc(p["tech"]) + "}"
            out.append(r"  \resumeProjectHeading{" + title + "}{" + esc(p.get("dates")) + "}")
            bullets = [b for b in (p.get("bullets") or []) if b.strip()]
            if bullets:
                out.append(r"    \resumeItemListStart")
                for b in bullets:
                    out.append(r"      \resumeItem{" + esc(b) + "}")
                out.append(r"    \resumeItemListEnd")
        out.append(r"\resumeSubHeadingListEnd")

    skills = data.get("skills") or []
    if skills:
        out.append("\n\\section{Technical Skills}")
        out.append(r"\begin{itemize}[leftmargin=0.15in, label={}]")
        out.append(r"  \small{\item{")
        for i, s in enumerate(skills):
            line = r"   \textbf{" + esc(s.get("category")) + "}{: " + esc(s.get("items")) + "}"
            if i < len(skills) - 1:
                line += r" \\"
            out.append(line)
        out.append(r"  }}")
        out.append(r"\end{itemize}")

    out.append("\n\\end{document}")
    return JAKE_PREAMBLE + "\n" + "\n".join(out) + "\n"


# ---------- Jake-template LaTeX -> structured content ----------

def _strip_tex(s: str) -> str:
    s = re.sub(r"\\href\{[^}]*\}\{\\underline\{([^}]*)\}\}", r"\1", s)
    s = re.sub(r"\\textbf\{([^}]*)\}", r"\1", s)
    s = re.sub(r"\\emph\{([^}]*)\}", r"\1", s)
    s = s.replace(r"\&", "&").replace(r"\%", "%").replace(r"\$|\$", "|")
    s = s.replace(r"\_", "_").replace(r"\#", "#").strip()
    return s


def parse_jake_latex(tex: str) -> dict:
    """Best-effort parse of LaTeX matching the Jake's template structure."""
    data = {"name": "", "phone": "", "email": "", "linkedin": "", "github": "",
            "website": "", "summary": "", "education": [], "experience": [],
            "projects": [], "skills": []}

    m = re.search(r"\\textbf\{\\Huge\s+\\scshape\s+(.+?)\}", tex)
    if m:
        data["name"] = _strip_tex(m.group(1))

    m = re.search(r"\\begin\{center\}(.+?)\\end\{center\}", tex, re.DOTALL)
    if m:
        block = m.group(1)
        m2 = re.search(r"\\small\s+([^\n]+)", block)
        if m2:
            for part in re.split(r"\$\|\$|\|", m2.group(1)):
                val = _strip_tex(part)
                if not val:
                    continue
                if "@" in val and not data["email"]:
                    data["email"] = val
                elif "linkedin" in val and not data["linkedin"]:
                    data["linkedin"] = val
                elif "github" in val and not data["github"]:
                    data["github"] = val
                elif (val[0].isdigit() or val.startswith("+")) and not data["phone"]:
                    data["phone"] = val
                elif not data["website"]:
                    data["website"] = val

    section = None
    last_entry = None
    for line in tex.splitlines():
        line = line.strip()
        m = re.match(r"\\section\{(.+)\}", line)
        if m:
            section = m.group(1).lower()
            last_entry = None
            continue
        m = re.match(r"\\resumeSubheading\{(.*)\}\{(.*)\}\{(.*)\}\{(.*)\}", line)
        if m:
            a, b, c, d = (_strip_tex(x) for x in m.groups())
            entry = {}
            if "education" in (section or ""):
                entry = {"school": a, "location": b, "degree": c, "dates": d}
                data["education"].append(entry)
            else:
                entry = {"company": a, "location": b, "title": c, "dates": d, "bullets": []}
                data["experience"].append(entry)
            last_entry = entry
            continue
        m = re.match(r"\\resumeProjectHeading\{(.*)\}\{(.*)\}", line)
        if m:
            head, dates = m.groups()
            head = _strip_tex(head)
            name_part, tech_part = head, ""
            if "|" in head:
                name_part, tech_part = (x.strip() for x in head.split("|", 1))
            name_part = name_part.rstrip(" $").strip()
            tech_part = tech_part.lstrip(" $").strip()
            entry = {"name": name_part, "tech": tech_part, "dates": _strip_tex(dates), "bullets": []}
            data["projects"].append(entry)
            last_entry = entry
            continue
        m = re.match(r"\\resumeItem\{(.*)\}", line)
        if m and last_entry is not None:
            last_entry.setdefault("bullets", []).append(_strip_tex(m.group(1)))
            continue
        m = re.match(r"\\textbf\{(.+?)\}\{:\s*(.+)\}", line)
        if m and "skill" in (section or ""):
            data["skills"].append({"category": _strip_tex(m.group(1)), "items": _strip_tex(m.group(2))})
            continue
        if section and "summary" in section and line and not line.startswith("\\"):
            data["summary"] = (_strip_tex(line) + " " + data["summary"]).strip() if data["summary"] else _strip_tex(line)

    return data


def parse_generic_latex(tex: str) -> str:
    """Convert arbitrary LaTeX source into editable document HTML (best effort)."""
    # strip preamble and comments
    m = re.search(r"\\begin\{document\}(.*)\\end\{document\}", tex, re.DOTALL)
    body = m.group(1) if m else tex
    body = re.sub(r"(?m)^%.*$", "", body)

    # lists -> html
    def _itemize(mm):
        items = re.split(r"\\item\s*", mm.group(1))[1:]
        lis = "".join(f"<li>{it.strip()}</li>" for it in items if it.strip())
        return f"<ul>{lis}</ul>"

    body = re.sub(r"\\begin\{itemize\}(.*?)\\end\{itemize\}", _itemize, body, flags=re.DOTALL)
    body = re.sub(r"\\begin\{enumerate\}(.*?)\\end\{enumerate\}", _itemize, body, flags=re.DOTALL)

    # sections/subsections
    body = re.sub(r"\\section\*?\{([^}]*)\}", r"\n<h2>\1</h2>\n", body)
    body = re.sub(r"\\subsection\*?\{([^}]*)\}", r"\n<h2>\1</h2>\n", body)

    # common formatting
    body = re.sub(r"\\textbf\{([^}]*)\}", r"<strong>\1</strong>", body)
    body = re.sub(r"\\textit\{([^}]*)\}", r"<em>\1</em>", body)
    body = re.sub(r"\\emph\{([^}]*)\}", r"<em>\1</em>", body)
    body = re.sub(r"\\underline\{([^}]*)\}", r"\1", body)
    body = re.sub(r"\\href\{[^}]*\}\{([^}]*)\}", r"\1", body)
    body = re.sub(r"\\url\{([^}]*)\}", r"\1", body)

    # macros with arguments we don't need -> keep their content or drop
    body = re.sub(r"\\(vspace|hspace|hfill|smallskip|bigskip)\{?[^}]*\}?", " ", body)
    body = re.sub(r"\\(centering|raggedright|large|Large|small|Huge|normalsize|scshape|bfseries|itshape)\b", " ", body)
    body = re.sub(r"\\resumeItem\{([^}]*)\}", r"<li>\1</li>", body)
    body = re.sub(r"\\resumeSubheading\{([^}]*)\}\{([^}]*)\}\{([^}]*)\}\{([^}]*)\}",
                  r'<div class="entry"><p class="er"><strong>\1</strong><span class="r">\2</span></p><p class="er sub"><em>\3</em><span class="r">\4</span></p></div>', body)
    body = re.sub(r"\\resumeProjectHeading\{([^}]*)\}\{([^}]*)\}",
                  r'<div class="entry"><p class="er"><strong>\1</strong><span class="r">\2</span></p></div>', body)
    body = re.sub(r"\\resumeSubHeadingListStart|\\resumeSubHeadingListEnd|\\resumeItemListStart|\\resumeItemListEnd|\\begin\{center\}|\\end\{center\}", "", body)

    # escaped chars
    for a, b in [(r"\&", "&"), (r"\%", "%"), (r"\$", "$"), (r"\_", "_"), (r"\#", "#"), (r"\{", "{"), (r"\}", "}"), (r"\\\\", "\n"), (r"\\\\ ", "\n")]:
        body = body.replace(a, b)

    # remaining backslash commands: drop the command, keep args text
    body = re.sub(r"\\[a-zA-Z@]+\*?", " ", body)
    body = re.sub(r"[ \t]+", " ", body)

    # paragraphs: split into <p> blocks, keep h2/ul/div/li tags intact
    out = []
    for chunk in re.split(r"\n\s*\n", body):
        chunk = chunk.strip()
        if not chunk:
            continue
        if re.match(r"^<(h2|ul|div|/div|/ul|li)>", chunk) or chunk.startswith("</"):
            out.append(chunk)
        else:
            for sub in chunk.split("\n"):
                sub = sub.strip()
                if sub.startswith("<"):
                    out.append(sub)
                elif sub:
                    out.append(f"<p>{sub}</p>")
    html = "\n".join(out)
    html = re.sub(r"\n{2,}", "\n", html)
    # attempt to name header: first strong/h2
    return html


TEMPLATE_RENDERERS = {"jakes": render_jake}


# ---------- editable-document HTML -> LaTeX ----------

def _inline_latex(node) -> str:
    """Convert inline HTML (text, b/strong, i/em, br) to LaTeX."""
    out = []
    for child in node.children:
        if isinstance(child, NavigableString):
            out.append(esc(str(child)))
        else:
            name = child.name.lower()
            if name in ("b", "strong"):
                out.append(r"\textbf{" + _inline_latex(child) + "}")
            elif name in ("i", "em"):
                out.append(r"\emph{" + _inline_latex(child) + "}")
            elif name == "br":
                out.append(r" \\ ")
            else:
                out.append(_inline_latex(child))
    return "".join(out)


def _entry_to_latex(entry) -> list[str]:
    lines = []
    head = entry.find("p", class_="er")
    sub = entry.find("p", class_="er sub")
    left = head.find(["strong", "b"]) if head else None
    right = head.find(class_="r") if head else None
    sleft = sub.find(["em", "i"]) if sub else None
    sright = sub.find(class_="r") if sub else None
    lines.append("  \\resumeSubheading{" + (_inline_latex(left) if left else "") + "}{" +
                 (_inline_latex(right) if right else "") + "}{" +
                 (_inline_latex(sleft) if sleft else "") + "}{" +
                 (_inline_latex(sright) if sright else "") + "}")
    bullets = [li for li in entry.find_all("li")]
    if bullets:
        lines.append(r"    \resumeItemListStart")
        for li in bullets:
            lines.append(r"      \resumeItem{" + _inline_latex(li) + "}")
        lines.append(r"    \resumeItemListEnd")
    return lines


def html_to_latex(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    out = []
    skills = []  # grouped at end
    contact = None
    name_html = None
    entries_open = False

    def close_entries():
        nonlocal entries_open
        if entries_open:
            out.append(r"\resumeSubHeadingListEnd")
            entries_open = False

    for el in soup.find_all(recursive=False):
        name = el.name.lower() if el.name else ""
        if name == "h1":
            name_html = _inline_latex(el)
        elif name == "p" and "contact" in (el.get("class") or []):
            contact = _inline_latex(el)
        elif name == "h2":
            close_entries()
            if skills:
                out.extend(_emit_skills(skills)); skills = []
            out.append("\n\\section{" + _inline_latex(el) + "}")
        elif name == "div" and "entry" in (el.get("class") or []):
            if skills:
                out.extend(_emit_skills(skills)); skills = []
            if not entries_open:
                out.append(r"\resumeSubHeadingListStart")
                entries_open = True
            out.extend(_entry_to_latex(el))
        elif name == "p" and "skill" in (el.get("class") or []):
            close_entries()
            skills.append(el)
        elif name == "ul":
            close_entries()
            if skills:
                out.extend(_emit_skills(skills)); skills = []
            out.append(r"\begin{itemize}")
            for li in el.find_all("li", recursive=False):
                out.append(r"  \item " + _inline_latex(li))
            out.append(r"\end{itemize}")
        elif name == "p":
            close_entries()
            if skills:
                out.extend(_emit_skills(skills)); skills = []
            text = _inline_latex(el).strip()
            if text:
                out.append(text + "\n")

    close_entries()
    if skills:
        out.extend(_emit_skills(skills))

    header = [r"\begin{document}", "", r"\begin{center}"]
    if name_html:
        header.append(r"    \textbf{\Huge \scshape " + name_html + r"} \\ \vspace{1pt}")
    if contact:
        header.append(r"    \small " + contact)
    header.append(r"\end{center}")
    body = header + out + ["", r"\end{document}"]
    return JAKE_PREAMBLE + "\n" + "\n".join(body) + "\n"


def _emit_skills(skill_els) -> list[str]:
    lines = [r"\begin{itemize}[leftmargin=0.15in, label={}]", r"  \small{\item{"]
    for i, el in enumerate(skill_els):
        b = el.find(["b", "strong"])
        rest = _inline_latex(el)
        if b:
            rest = _inline_latex(el)
        line = "   " + rest
        if i < len(skill_els) - 1:
            line += r" \\"
        lines.append(line)
    lines.append(r"  }}")
    lines.append(r"\end{itemize}")
    return lines


def find_pdflatex() -> str | None:
    exe = shutil.which("pdflatex")
    if exe:
        return exe
    candidates = [
        Path(r"C:\Program Files\MiKTeX\miktex\bin\x64\pdflatex.exe"),
        Path(r"C:\Program Files (x86)\MiKTeX\miktex\bin\pdflatex.exe"),
        Path.home() / r"AppData\Local\Programs\MiKTeX\miktex\bin\x64\pdflatex.exe",
    ]
    for c in candidates:
        if c.exists():
            return str(c)
    return None


class LatexError(Exception):
    def __init__(self, message: str, log: str = ""):
        super().__init__(message)
        self.log = log


def compile_latex(tex_source: str, engine: str | None = None) -> bytes:
    exe = engine or find_pdflatex()
    if not exe:
        raise LatexError(
            "No LaTeX compiler found. Install MiKTeX (winget install MiKTeX.MiKTeX) or TeX Live."
        )
    with tempfile.TemporaryDirectory() as tmp:
        tex_path = Path(tmp) / "resume.tex"
        tex_path.write_text(tex_source, encoding="utf-8")
        proc = subprocess.run(
            [exe, "-interaction=nonstopmode", "-halt-on-error", "-no-shell-escape", "resume.tex"],
            cwd=tmp, capture_output=True, text=True, timeout=120,
        )
        pdf_path = Path(tmp) / "resume.pdf"
        if pdf_path.exists() and pdf_path.stat().st_size > 0 and proc.returncode == 0:
            return pdf_path.read_bytes()
        log = (proc.stdout or "") + "\n" + (proc.stderr or "")
        # extract the first error context
        m = re.search(r"(! .+?)\n!+", log, re.DOTALL)
        brief = m.group(1)[:800] if m else log[-1500:]
        raise LatexError(f"LaTeX compilation failed: {brief}", log=log[-4000:])
