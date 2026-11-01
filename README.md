# 🚀 CBIT Hacktoberfest '26 — Project Starter Repository

> **Official Public Starter Repository for CBIT Hacktoberfest '26**  
> *Chaitanya Bharathi Institute of Technology (CBIT), Hyderabad*

---

## 📋 Team Information

| Attribute | Details |
| :--- | :--- |
| **Team Name** | **JL** |
| **Team Number** | `TEAM-41` (`HFT26-TEAM-41`) |
| **Registration ID** | `HFEST26-GLZMC5TB` |
| **Problem Track** | **Track Selection in Progress** |
| **Domain** | `General Track` |
| **Team Leader** | Sriram aditya sai (sriramaditya996@gmail.com) |
| **Institution** | CBIT |

### 👥 Team Members

| # | Name | Email | Institution |
| :--- | :--- | :--- | :--- |
| 1 | G Anish | anish.g1835@gmail.com | CBIT |
| 2 | Faiz | syedfaizahmedbasha@gmail.com | CBIT |

---

## 🎯 Problem Statement

### **Portfolio-Driven Adaptive Coding & Technical Assessment Platform**
*Domain:* **General Track**

Static coding tests ignore a candidate's background, and AI coding tools make it
hard to tell whether candidates understand the work in their portfolio. We turn a
candidate's structured JSON portfolio (projects, stack, skills, DSA topics solved)
into a validated 60-minute assessment in their own domain and stack: one domain task
and one DSA task, at a Novice, Adept or Master tier. Every task is checked before
release (the reference passes, the starter fails), candidate code runs in isolated
sandboxes, and grading is deterministic: tests decide correctness, never an LLM.
Adept and Master tiers get a guarded AI assistant whose efficient use counts for up
to 20% of the score, and the report shows task-wise metrics, pass rates and time.

---

## 🛠️ Contribution & Submission Workflow

All teams must follow the official fork-and-pull-request workflow:

1. **Fork this Repository**:
   - One team member should click the **Fork** button at the top right to fork this upstream repository to your personal/team GitHub account.
2. **Add Collaborators**:
   - In your forked repository, navigate to **Settings > Collaborators** and invite all your registered team members.
3. **Clone & Develop Locally**:
   ```bash
   git clone https://github.com/<your-username>/HFT26-TEAM-41.git
   cd HFT26-TEAM-41
   git checkout -b feature/prototype
   ```
4. **Commit & Push Regularly**:
   - Make atomic, descriptive commits throughout the hackathon.
   ```bash
   git add .
   git commit -m "feat: implement core solution architecture"
   git push origin feature/prototype
   ```
5. **Open Pull Request (PR) for Final Submission**:
   - When ready for evaluation, open a **Pull Request** from your fork's `main` branch back to this upstream repository's `main` branch.
   - **PR Title Format**: `[SUBMISSION] TEAM-41 - JL - Track Selection in Progress`
   - **PR Description Checklist**:
     - 📌 Solution Overview & Approach
     - 🏗️ Architecture & Tech Stack Details
     - 🚀 Local Setup & Installation Instructions
     - 🎥 Demo Video Link / Live Deployment URL
     - 📸 Key Screenshots & Visuals

---

## 📁 Project Structure

Our code lives in these folders at the root, instead of the starter's suggested `src/`:

```
.
├── backend/              # FastAPI API, Celery workers, LLM client, runner, tests
├── frontend/             # Next.js app (recruiter, candidate IDE, report, interview)
├── contracts/            # JSON Schemas shared by backend and frontend, with fixtures
├── seeds/                # Hand-written, tested seed repos that tasks are built from
├── dsa/                  # DSA problem bank, JSON test cases, runners per language
├── runtimes/             # Dockerfiles for the sandboxed runner images
├── sim/                  # Simulated candidate scripts
├── docs/                 # Blueprint, build prompts, progress, interviewer spec
├── README.md
└── LICENSE               # MIT
```

---

## 📌 Solution Overview

*To be completed.*

## 🏗️ Architecture & Tech Stack

*To be completed.*

## 🚀 Local Setup

The platform is four parts that run side by side:

| Part | Folder | What it is | Run it |
| --- | --- | --- | --- |
| Landing site | `showcase/` | Static site "Assay": overview, **Code reading** (`/comprehension`) and **AI mock interview** (`/interview`), both in the browser | `cd showcase && npm ci && npm run dev` (port 3001) |
| Practice problems | `frontend/` + `backend/` | LeetCode-style problem list and Monaco editor (`/practice`); Run, custom input and Submit in a sandbox | `cp .env.example .env`, `make runtimes`, `make up`, `make migrate`; open http://localhost:3000/practice |
| Assessment engine | `backend/`, `frontend/app/session`, `frontend/app/report` | Portfolio to validated 60-minute assessment, sandbox grading, report | `make seed-demo` prints a session URL |
| Code comprehension app | `code-compr/` | Full code-reading app (GitHub task curation, rubric review, Prisma) | see `code-compr/.env.example`; `npm install`, `npm run db:push`, `npm run dev` (port 3002) |

The landing site links to the practice app at `NEXT_PUBLIC_PRACTICE_URL`
(default `http://localhost:3000/practice`), and the practice app's navigation links back
to the landing site, the code-reading app and the AI interview through
`NEXT_PUBLIC_SHOWCASE_URL` (default `http://localhost:3001`) and
`NEXT_PUBLIC_CODE_READING_URL` (default `http://localhost:3002`). `coding-assessment/`, an earlier standalone
prototype (Express, Judge0, MongoDB), is archived on the `archive/coding-assessment` branch;
the practice mode in `frontend/` replaces it.
The in-site AI interview is browser-only (Web Speech API, scripted questions); the
model-backed interviewer in `docs/INTERVIEWER.md` is not built yet.

## 🎥 Demo Video

*To be completed.*

## 📸 Screenshots

*To be completed.*

---

## ⚠️ Important Rules & Code of Conduct
* **Upstream Protection**: Do not push directly to this repository's main branch. All evaluation will be conducted on your submitted Pull Request.
* **Original Work**: All code submitted must be developed during the hackathon timeline. Open-source libraries and frameworks are welcomed with proper attribution.
* **Code Freeze**: Final Pull Requests must be submitted before the designated hackathon submission deadline.
