# Development

```console
git clone https://github.com/oec-tech/ya-onelogin-aws-assume-role
cd ya-onelogin-aws-assume-role
uv venv && uv pip install -e ".[dev]"     # or: python -m venv .venv && pip install -e ".[dev]"
python -m unittest discover -s tests      # tests
ruff check src tests                      # lint
```

CI runs the tests on Python 3.10 to 3.14 on Linux and on Windows and macOS,
the linter, and builds and installs the wheel.

## Documentation

These pages are built with [Zensical](https://zensical.org/) from `docs/` and
`zensical.toml`:

```console
uv pip install zensical
zensical serve      # preview on http://localhost:8000
zensical build      # writes site/
```

Pushes to `master` publish the site to GitHub Pages (enable Pages with
**Source: GitHub Actions** in the repository settings once).

## Releasing

Update the version in `src/aws_assume_role/version.py`, then publish a GitHub
release tagged `v<version>`; the *Publish to PyPI* workflow builds and uploads
it as `ya-onelogin-aws-assume-role`. Before the first release, create that
project on PyPI and add this repository's `publish.yml` as its Trusted
Publisher; until then, install from git.
