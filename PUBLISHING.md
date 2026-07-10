# Publishing Aurelius to PyPI

The package builds and validates cleanly and installs from the wheel in a fresh venv.
The final `twine upload` step is left to you because it is **public and irreversible**
(a version number can never be reused) and needs *your* PyPI credentials.

- **Distribution name:** `aurelius-mcp` (the bare `aurelius` is already taken on PyPI).
- **Import name / CLI command:** `aurelius` (unchanged).

## 0. One-time setup
1. Create accounts: <https://pypi.org/account/register/> and <https://test.pypi.org/account/register/>.
2. Create an **API token** for each (Account settings → API tokens). Scope it to the
   project after the first upload; for the first upload use an account-wide token.
3. Either paste the token when prompted, or create `~/.pypirc`:
   ```ini
   [pypi]
     username = __token__
     password = pypi-AgEI...your-token...

   [testpypi]
     username = __token__
     password = pypi-AgEI...your-testpypi-token...
   ```

## 1. Build (already done, but to rebuild)
```bash
cd Aurelius
rm -rf dist build src/*.egg-info
python -m build
python -m twine check dist/*        # must say PASSED for both artifacts
```

## 2. Dry run on TestPyPI (recommended)
```bash
python -m twine upload --repository testpypi dist/*
```
Then install from TestPyPI in a clean venv to confirm it works publicly:
```bash
python -m venv /tmp/aurtest && /tmp/aurtest/Scripts/python -m pip install \
  --index-url https://test.pypi.org/simple/ \
  --extra-index-url https://pypi.org/simple/ \
  aurelius-mcp
/tmp/aurtest/Scripts/python -c "import aurelius; print(aurelius.__version__)"
```
(The `--extra-index-url` lets it pull real deps `mcp`/`httpx` from real PyPI.)

## 3. Publish to PyPI (the real, irreversible step)
```bash
python -m twine upload dist/*
```
Your package is then live: `pip install aurelius-mcp`.

## 4. Releasing new versions
- Bump `version` in `pyproject.toml` (PyPI rejects re-uploading an existing version).
- Rebuild, `twine check`, upload.
- Tag the release: `git tag v0.1.0 && git push --tags`.

## Pre-publish checklist
- [ ] `version` bumped if this isn't the first upload
- [ ] `twine check dist/*` → PASSED
- [ ] Installed the wheel in a clean venv and imported it
- [ ] `[project.urls]` in `pyproject.toml` points at your real repo (currently a placeholder)
- [ ] Author name/email set in `pyproject.toml` if you want them public
