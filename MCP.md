# Publishing an MCP Server package

How to publish this project to PyPI so anyone can run it with `uvx candidate-skill-agent`.

Registries: **[PyPI](https://pypi.org)** (real) and **[TestPyPI](https://test.pypi.org)**
(a throwaway copy to rehearse on). Runner tools: `uvx` (Python), `npx` (Node).

> **Before publishing:** this package depends on `labs-agent-lib`, which itself is **not yet
> on the real PyPI** (only on TestPyPI). Anyone installing `candidate-skill-agent` from the
> real PyPI with `uvx`/`pip` will need `--extra-index-url https://test.pypi.org/simple/`
> until `labs-agent-lib` graduates too — see the install examples below.

---

## 1. Create your accounts (once)

You need **two separate accounts** — TestPyPI does not share logins with PyPI:

1. Register at https://pypi.org/account/register/ and https://test.pypi.org/account/register/
2. **Verify your email** on both.
3. **Enable 2FA** (Account settings → Two-factor authentication). PyPI *requires* it to upload.

## 2. (Optional) Create an organization

Use an org when the package is owned by a team/company rather than you personally, so
membership and permissions outlive any single account.

- Go to **Your organizations → Add organization**, pick a name, then invite members and
  assign the project to it.
- Skip this for personal packages — a plain account marked "sole owner" (as in this repo) is fine.

## 3. Prepare the package metadata (once)

`pyproject.toml` must have these for a clean upload — already set in this repo:

| Field                      | Why it's needed                                                   |
| -------------------------- | ------------------------------------------------------------------ |
| `name`                   | Must be **globally unique** on PyPI (check the project URL).      |
| `version`                | Immutable once uploaded — bump it every release.                  |
| `description`,`readme` | Shown on the project page.                                         |
| `license` + `LICENSE`  | Legal terms; the file must match the declared license.             |
| `[project.scripts]`      | Makes it runnable as a command (`uvx candidate-skill-agent`).    |

## 4. Get an API token

PyPI no longer accepts username/password for uploads — you upload with a **token**.

1. Go to **Account settings → API tokens → Add API token**
   (https://pypi.org/manage/account/token/, and the same on TestPyPI).
2. First release: scope = **"Entire account"** (the project doesn't exist yet, so you
   can't scope to it). After the first upload, delete it and create one **scoped to
   `candidate-skill-agent`** — least privilege.
3. Copy the token (starts with `pypi-…`) **now** — it's shown only once.

### How to manage the token safely

- **Never commit it** or paste it into `pyproject.toml`. Treat it like a password.
- Pass it per-command with `--token`, or export it once per shell session:

  ```sh
  export UV_PUBLISH_TOKEN=pypi-xxxxxxxx      # uv reads this automatically
  ```
- If it leaks, **revoke it** in Account settings and create a new one.
- Prefer a **project-scoped** token for day-to-day releases.

## 5. Build the distribution

```sh
rm -rf dist/     # avoid uploading stale versions
uv build         # creates dist/*.tar.gz (source) and dist/*.whl (wheel)
```

## 6. Publish to TestPyPI first (rehearsal)

Verifies the upload + install work without touching the real index.

```sh
# upload
uv publish --publish-url https://test.pypi.org/legacy/ --token pypi-<TESTPYPI_TOKEN>

# verify it installs and runs from TestPyPI.
# --extra-index-url is required: TestPyPI lacks real deps (mcp, langchain, labs-agent-lib, ...),
# so they must resolve from the real PyPI as a fallback (labs-agent-lib is the exception —
# it only exists on TestPyPI, so this direction happens to "just work" here).
uvx --index-url https://test.pypi.org/simple/ \
    --extra-index-url https://pypi.org/simple/ \
    candidate-skill-agent --protocol stdio
```

## 7. Publish to the real PyPI

```sh
uv publish --token pypi-<PYPI_TOKEN>
```

Verify (note the extra index — `labs-agent-lib` only lives on TestPyPI today):

```sh
uvx --index-url https://pypi.org/simple/ \
    --extra-index-url https://test.pypi.org/simple/ \
    candidate-skill-agent --protocol stdio
```

## 8. Release a new version

`0.1.0` can never be re-uploaded. For any change:

1. Bump `version` in `pyproject.toml` (e.g. `0.1.1`).
2. Repeat steps **5 → 7**.

---

## Use the published server (MCP client config)

**From PyPI** (needs the TestPyPI extra index until `labs-agent-lib` is on the real PyPI):

```json
{
  "mcpServers": {
    "candidate-skill-agent": {
      "command": "uvx",
      "args": [
        "--index-url", "https://pypi.org/simple/",
        "--extra-index-url", "https://test.pypi.org/simple/",
        "candidate-skill-agent", "--protocol", "stdio"
      ]
    }
  }
}
```

**From a GitHub repo (no publish needed):**

```json
{
  "mcpServers": {
    "candidate-skill-agent": {
      "command": "uvx",
      "args": [
        "--from", "git+https://github.com/albertbolanoss/candidate-skill-agent",
        "candidate-skill-agent", "--protocol", "stdio"
      ]
    }
  }
}
```
