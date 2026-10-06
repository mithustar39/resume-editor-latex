# Resume Editor

A web app for writing LaTeX resumes without LaTeX syntax.
Edit in a document-style form editor, or drop into raw LaTeX — both compile to
the same professional PDF (Jake's Resume template built in).

## Features

- **Two editing modes**
  - *Document Editor* — Google-Docs-style form for personal info, education,
    experience, projects, and skills. Generates LaTeX automatically.
  - *Raw LaTeX* — a plain-text editor for full control with live PDF preview.
- **Live PDF preview** with one-click download.
- **Accounts** — register/login, resumes are saved per-user in SQLite.
- Powered by FastAPI + SQLAlchemy on the backend, plain HTML/CSS/JS frontend.

## Setup

```bash
pip install -r requirements.txt
```

You also need a LaTeX compiler. On Windows, the easiest option:

```bash
winget install MiKTeX.MiKTeX
```

MiKTeX will auto-download required LaTeX packages on first compile.

## Run

```bash
cd backend
python -m uvicorn main:app --reload
```

Open http://localhost:8000, register an account, and start writing.

## Project structure

```
backend/
  main.py        FastAPI routes (auth, resumes CRUD, /api/compile)
  auth.py        JWT + bcrypt authentication
  db.py          SQLite models (User, Resume)
  latex.py       Jake's-template renderer + pdflatex wrapper
  static/        Frontend (index.html, app.js, style.css)
data/            SQLite database (created at runtime)
```
