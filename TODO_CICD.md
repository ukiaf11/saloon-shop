# Task list — repo push, CI/CD, GitHub Pages fallback

Target repo: `https://github.com/ukiaf11/saloon-shop`

## 1. Secret safety (before any commit)
- [x] Confirm `.gitignore` excludes root `.env` (holds the GitHub PAT), `backend/.env`
      (Django SECRET_KEY, seed password), `frontend/.env.local`
- [x] Stage everything, then scan the **staged tree** for secrets before committing
- [x] Confirm no `.venv/`, `node_modules/`, `.next/`, `__pycache__/`, media uploads staged
- [x] Push using an ephemeral credential helper so the token never lands in
      `.git/config`, the remote URL, or the reflog

## 2. Initial push
- [x] `git init`, branch `main`
- [x] Commit Phases 1–2 with an honest message
- [x] Push to `origin/main`
- [x] Verify the pushed tree on GitHub contains no secrets

## 3. CI (already drafted in `.github/workflows/ci.yml` — verify it runs green)
- [x] Backend: ruff, format check, migration check, django check, pytest (Postgres + Redis services)
- [x] Frontend: lint, typecheck, format check, vitest, build
- [x] Security: gitleaks, pip-audit, npm audit
- [x] Docker: build both prod images
- [x] Fix whatever fails on the real runner

## 4. CD — container images
- [x] On push to `main`: build and push backend + frontend images to GHCR
- [x] Tag by commit SHA and `latest`
- [x] Use the built-in `GITHUB_TOKEN` (no extra secret needed)

## 5. CD — GitHub Pages fallback
- [x] Static export of the Next frontend (`output: 'export'` behind a flag)
- [x] Handle what static export breaks: ISR/revalidate, `next/image` optimizer,
      and the fact that **there is no Django backend on Pages**
- [x] Deploy via `actions/deploy-pages`
- [x] Document precisely what the Pages build is and is not

## 6. Docs
- [x] README: badges, deployment section, how to point the Pages build at a live API
- [x] memory.md: record the CI/CD setup and the Pages limitations

## 7. Handover
- [x] Tell the user to revoke the exposed PAT and issue a new one
- [x] List any repo settings they must set by hand (Pages source, Actions permissions)


---

## Status: complete (2026-09-20)

All three workflows green on `cf6ab64`.

- Repo: <https://github.com/ukiaf11/saloon-shop> — 208 files, no secrets pushed
- Images: `ghcr.io/ukiaf11/saloon-shop/{backend,frontend}` tagged `latest`, `main`, `sha-…`
- Pages: <https://ukiaf11.github.io/saloon-shop/> — live, noindex

### Left for the repo owner

- [ ] **Revoke the PAT** used for the initial push (it was shared in chat and in
      a screenshot, and carries `admin:org` / `admin:enterprise` / `write:packages`).
      Issue a replacement scoped to `repo` only if one is still needed.
- [ ] Decide whether the GHCR packages should be public (they default to private
      even on a public repo).
- [ ] Set `PUBLIC_API_BASE_URL` once an API is publicly reachable, or the Pages
      preview stays empty.
