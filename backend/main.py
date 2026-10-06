import json
from pathlib import Path

from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

import auth
from db import get_db, init_db, User, Resume
from latex import render_jake, compile_latex, LatexError, TEMPLATE_RENDERERS, find_pdflatex

app = FastAPI(title="Resume Editor")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

STATIC_DIR = Path(__file__).resolve().parent / "static"


@app.on_event("startup")
def startup():
    init_db()


# ---------- auth ----------

class RegisterIn(BaseModel):
    email: str
    password: str


class LoginIn(BaseModel):
    email: str
    password: str


@app.post("/api/register")
def register(body: RegisterIn, db: Session = Depends(get_db)):
    if len(body.password) < 6:
        raise HTTPException(400, "Password must be at least 6 characters")
    if db.query(User).filter(User.email == body.email.lower()).first():
        raise HTTPException(400, "Email already registered")
    user = User(email=body.email.lower(), password_hash=auth.hash_password(body.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"token": auth.create_token(user.id), "email": user.email}


@app.post("/api/login")
def login(body: LoginIn, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == body.email.lower()).first()
    if not user or not auth.verify_password(body.password, user.password_hash):
        raise HTTPException(401, "Invalid email or password")
    return {"token": auth.create_token(user.id), "email": user.email}


# ---------- resumes ----------

class ResumeIn(BaseModel):
    title: str = "Untitled Resume"
    template: str = "jakes"
    content: dict = {}
    raw_latex: str | None = None


def resume_out(r: Resume) -> dict:
    try:
        content = json.loads(r.content or "{}")
    except json.JSONDecodeError:
        content = {}
    return {"id": r.id, "title": r.title, "template": r.template,
            "content": content, "raw_latex": r.raw_latex,
            "updated_at": r.updated_at.isoformat() if r.updated_at else None}


@app.get("/api/resumes")
def list_resumes(user: User = Depends(auth.current_user), db: Session = Depends(get_db)):
    rows = db.query(Resume).filter(Resume.user_id == user.id).order_by(Resume.updated_at.desc()).all()
    return [resume_out(r) for r in rows]


@app.post("/api/resumes")
def create_resume(body: ResumeIn, user: User = Depends(auth.current_user), db: Session = Depends(get_db)):
    r = Resume(user_id=user.id, title=body.title, template=body.template,
               content=json.dumps(body.content), raw_latex=body.raw_latex)
    db.add(r)
    db.commit()
    db.refresh(r)
    return resume_out(r)


@app.get("/api/resumes/{rid}")
def get_resume(rid: int, user: User = Depends(auth.current_user), db: Session = Depends(get_db)):
    r = db.get(Resume, rid)
    if not r or r.user_id != user.id:
        raise HTTPException(404, "Not found")
    return resume_out(r)


@app.put("/api/resumes/{rid}")
def update_resume(rid: int, body: ResumeIn, user: User = Depends(auth.current_user), db: Session = Depends(get_db)):
    r = db.get(Resume, rid)
    if not r or r.user_id != user.id:
        raise HTTPException(404, "Not found")
    r.title = body.title
    r.template = body.template
    r.content = json.dumps(body.content)
    r.raw_latex = body.raw_latex
    db.commit()
    db.refresh(r)
    return resume_out(r)


@app.delete("/api/resumes/{rid}")
def delete_resume(rid: int, user: User = Depends(auth.current_user), db: Session = Depends(get_db)):
    r = db.get(Resume, rid)
    if not r or r.user_id != user.id:
        raise HTTPException(404, "Not found")
    db.delete(r)
    db.commit()
    return {"ok": True}


# ---------- compile ----------

class CompileIn(BaseModel):
    template: str = "jakes"
    content: dict = {}
    raw_latex: str | None = None


def build_tex(template: str, content: dict, raw_latex: str | None) -> str:
    if raw_latex and raw_latex.strip():
        return raw_latex
    if content.get("doc_html"):
        from latex import html_to_latex
        return html_to_latex(content["doc_html"])
    renderer = TEMPLATE_RENDERERS.get(template)
    if not renderer:
        raise HTTPException(400, f"Unknown template '{template}'")
    return renderer(content)


@app.post("/api/compile")
def compile_endpoint(body: CompileIn, user: User = Depends(auth.current_user)):
    tex = build_tex(body.template, body.content, body.raw_latex)
    try:
        pdf = compile_latex(tex)
    except LatexError as e:
        raise HTTPException(422, str(e))
    return Response(content=pdf, media_type="application/pdf")


@app.get("/api/status")
def status():
    return {"pdflatex": find_pdflatex()}


@app.post("/api/tex")
def tex_endpoint(body: CompileIn, user: User = Depends(auth.current_user)):
    tex = build_tex(body.template, body.content, body.raw_latex)
    return Response(content=tex, media_type="text/plain")


class ImportIn(BaseModel):
    raw_latex: str


@app.post("/api/import-latex")
def import_latex(body: ImportIn, user: User = Depends(auth.current_user)):
    from latex import parse_jake_latex, parse_generic_latex
    struct = parse_jake_latex(body.raw_latex)
    has_struct = any([struct["name"], struct["education"], struct["experience"], struct["projects"], struct["skills"]])
    if has_struct:
        return {"content": struct, "doc_html": "", "method": "parsed"}
    return {"content": struct, "doc_html": parse_generic_latex(body.raw_latex), "method": "generic"}


class AiImportIn(BaseModel):
    raw_latex: str
    api_key: str = ""


@app.post("/api/import-latex-ai")
def import_latex_ai(body: AiImportIn, user: User = Depends(auth.current_user)):
    key = body.api_key or __import__("os").environ.get("GOOGLE_API_KEY") or __import__("os").environ.get("GEMINI_API_KEY")
    if not key:
        raise HTTPException(400, "No Gemini API key. Set GOOGLE_API_KEY or paste one in the UI (free at aistudio.google.com).")
    import json as _json, urllib.request, urllib.error
    prompt = (
        "Convert the following resume LaTeX source into this exact JSON structure. "
        "Return ONLY valid JSON, no markdown, no code fences.\n"
        '{"name":"","phone":"","email":"","linkedin":"","github":"","website":"","summary":"",'
        '"education":[{"school":"","location":"","degree":"","dates":""}],'
        '"experience":[{"company":"","location":"","title":"","dates":"","bullets":[""]}],'
        '"projects":[{"name":"","tech":"","dates":"","bullets":[""]}],'
        '"skills":[{"category":"","items":""}]}\n\nLaTeX:\n' + body.raw_latex[:12000]
    )
    payload = _json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0, "responseMimeType": "application/json"},
    }).encode()
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={key}"
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            out = _json.loads(resp.read())
    except urllib.error.HTTPError as e:
        raise HTTPException(502, f"Gemini error: {e.code} {e.read()[:300].decode(errors='ignore')}")
    text = out["candidates"][0]["content"]["parts"][0]["text"].strip()
    try:
        return {"content": _json.loads(text), "doc_html": "", "method": "ai"}
    except _json.JSONDecodeError:
        # try to salvage a JSON block
        import re as _re
        mm = _re.search(r"\{.*\}", text, _re.DOTALL)
        if mm:
            try:
                return {"content": _json.loads(mm.group(0)), "doc_html": "", "method": "ai"}
            except Exception:
                pass
        raise HTTPException(502, "AI returned non-JSON; try again or use the free importer")


# frontend
app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
