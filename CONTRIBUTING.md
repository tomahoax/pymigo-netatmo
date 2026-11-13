# Contributing

Thank you for your interest in pymigo-netatmo. This guide covers the development setup
and the checks to run before opening a pull request.

## Development setup

Python 3.11 or later is required.

```sh
git clone https://github.com/tomahoax/pymigo-netatmo.git
cd pymigo-netatmo
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
```

To try the development version in another project without cloning:

```sh
python -m pip install git+https://github.com/tomahoax/pymigo-netatmo.git
```

## Checks before a pull request

```sh
ruff check .
ruff format --check .
mypy src
pytest --cov=pymigo_netatmo --cov-report=term-missing
```

All four commands must pass. The same checks run in the GitHub Actions workflow.

## Tests

`pymigo_netatmo.testing.FakeMigo` supports offline setup and writes. Tests must not
call the real Netatmo backend.

## Personal data

Captures and snapshots contain personal data. Redact them before sharing them in an
issue or a pull request. The normal logger already redacts payloads, and raw logging
requires an explicit `pymigo_netatmo.raw` debug level.

## Further reading

- [Architecture](docs/architecture.md)
- [API reference](docs/api/reference.md)
- [OpenAPI](openapi.yaml)
