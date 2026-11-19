# Working setup

How this project is set up and run. Versions as installed on 2026-11-18.

## Requirements

- Python 3.9, the oldest version XactFlow supports (developed on 3.9.25).
- Verilator, for linting the generated SystemVerilog (developed with 5.022).

## Virtual environment

The project has its own venv in `.venv/` (ignored by git). Created with:

```bash
git clone https://github.com/IP-XACT/XactFlow-rtlgen.git
cd XactFlow-rtlgen
python3.9 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install xactflow==0.4.0 ipxact-compiler==0.2.0 xactflow-archidesc==0.3.1 \
    xactflow-design==0.2.1 xactflow-component==0.2.1 pytest
pip install -e .
```

Activate it (`source .venv/bin/activate`) in every new terminal before running `xactflow`,
`python` or `pytest`.

| Package            | Version | What it is for                                                                               |
|--------------------|---------|----------------------------------------------------------------------------------------------|
| pip                | 26.0.1  | upgraded from 21.3.1, which is barely new enough for editable installs from `pyproject.toml` |
| xactflow           | 0.4.0   | XactFlow core: the CLI, `Library`, `link()`, the `Exporter` base class                       |
| ipxact-compiler    | 0.2.0   | the `ipxact` module: parses IP-XACT XML into Python objects                                  |
| lxml               | 6.1.3   | XML parser, pulled in by xactflow                                                            |
| xactflow-archidesc | 0.3.1   | importer: runs a Python design description (`design.py`)                                     |
| xactflow-design    | 0.2.1   | exporter: writes a design as IP-XACT XML                                                     |
| xactflow-component | 0.2.1   | exporter: writes the component holding a design as IP-XACT XML                               |
| pytest             | 8.4.2   | tests                                                                                        |
| rtlgen             | 0.0.1   | this project, installed editable (`pip install -e .`)                                        |

archidesc, design and component are only needed to make the inputs (see `inputs.md`).
The exporter itself depends only on xactflow and ipxact-compiler.

## The package

- `pyproject.toml`: the package `rtlgen`, version 0.0.1, depending on `xactflow>=0.4.0,<0.5`
  and `ipxact-compiler>=0.2.0`. The cap on xactflow is there because 0.4 broke the plugin API.
- `src/rtlgen/__init__.py`: the exporter class `RtlExporter`.
- The entry point `rtl = "rtlgen:RtlExporter"` in the group `xactflow.exporters` registers it.
  XactFlow's `discover_exporters()` finds it there and makes the subcommand `xactflow rtl`.
- The install is editable: the venv links to `src/`, so a change to the code takes effect the
  next time `xactflow` runs. Reinstall only when `pyproject.toml` changes.

## Running

```bash
source .venv/bin/activate
EX=$RTLGEN_EXAMPLE
LIBS="--lib $EX/xml_to_design --lib $EX/bus_definitions --lib build/soc_a"
xactflow rtl build/soc_a/example.org_design_soc_a.design_1.0.xml $LIBS --output build/soc_a/rtl
verilator --lint-only -Wno-PINMISSING --top-module soc_a build/soc_a/rtl/soc_a.sv $EX/sv_to_design/*.sv
```

The input files and `RTLGEN_EXAMPLE` are described in `inputs.md`. Verilator needs the
example's RTL of the five leaves (`$EX/sv_to_design/`) to check the instances against.
`-Wno-PINMISSING` stays until the ports are connected (steps 4 to 7). `-Wall` is left out: it
warns about unused and undriven signals inside the example's leaves, not in the output.

## Git

- `.gitignore` is GitHub's Python template. Among others it leaves out `build/`, `.venv/`,
  `*.egg-info/` and `__pycache__/`.
- Default branch `main`.

## Old exporter

[XactFlow-rtl-gen](https://github.com/joaln27/XactFlow-rtl-gen) is the earlier exporter. It is
used only as a black box to compare output against, never as code to copy. When a question it already met
comes up, its `docs/decisions.md` shows how it was decided then; this project decides again in
its own log.
