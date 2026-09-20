# Task list — repo push, CI/CD, GitHub Pages fallback

Target repo: `https://github.com/ukiaf11/saloon-shop`

## 1. Secret safety (before any commit)
- [ ] Confirm `.gitignore` excludes root `.env` (holds the GitHub PAT), `backend/.env`
      (Django SECRET_KEY, seed password), `frontend/.env.local`
- [ ] Stage everything, then scan the **staged tree** for secrets before committing
- [ ] Confirm no `.venv/`, `node_modules/`, `.next/`, `__pycache__/`, media uploads staged
- [ ] Push using an ephemeral credential helper so the token never lands in
      `.git/config`, the remote URL, or the reflog

## 2. Initial push
- [ ] `git init`, branch `main`
- [ ] Commit Phases 1–2 with an honest message
- [ ] Push to `origin/main`
- [ ] Verify the pushed tree on GitHub contains no secrets

## 3. CI (already drafted in `.github/workflows/ci.yml` — verify it runs green)
- [ ] Backend: ruff, format check, migration check, django check, pytest (Postgres + Redis services)
- [ ] Frontend: lint, typecheck, format check, vitest, build
- [ ] Security: gitleaks, pip-audit, npm audit
- [ ] Docker: build both prod images
- [ ] Fix whatever fails on the real runner

## 4. CD — container images
- [ ] On push to `main`: build and push backend + frontend images to GHCR
- [ ] Tag by commit SHA and `latest`
- [ ] Use the built-in `GITHUB_TOKEN` (no extra secret needed)

## 5. CD — GitHub Pages fallback
- [ ] Static export of the Next frontend (`output: 'export'` behind a flag)
- [ ] Handle what static export breaks: ISR/revalidate, `next/image` optimizer,
      and the fact that **there is no Django backend on Pages**
- [ ] Deploy via `actions/deploy-pages`
- [ ] Document precisely what the Pages build is and is not

## 6. Docs
- [ ] README: badges, deployment section, how to point the Pages build at a live API
- [ ] memory.md: record the CI/CD setup and the Pages limitations

## 7. Handover
- [ ] Tell the user to revoke the exposed PAT and issue a new one
- [ ] List any repo settings they must set by hand (Pages source, Actions permissions)
