# rtlgen

A [XactFlow](https://github.com/IP-XACT/XactFlow) exporter plugin that generates a
SystemVerilog top-level module from an IEEE 1685-2022 (IP-XACT) design.

It is being written step by step. Step 1 is done: the plugin is registered with XactFlow as
the `rtl` subcommand, links the design against its library, names the module from the
component that holds the design, and writes an empty module. Instances, parameters and
connections come in the next steps.

## Use

```bash
pip install -e .
xactflow rtl <design.xml> --lib <dir> [--lib <dir> ...] --output <dir>
```

It writes `<module>.sv` into the output folder. It refuses, with a message, anything it does
not handle yet: options, design configurations, a design that does not link, or a module name
it cannot find (see `docs/decisions.md`).

## Docs

- `docs/setup.md`: the development setup and how to run it.
- `docs/inputs.md`: the example design used as input, and how to generate it.
- `docs/decisions.md`: the decisions that shape the exporter, why they were made, and what
  would reopen them.

## Tests

```bash
pytest -q
```

The tests read the XactFlow author's example design from the clone that `RTLGEN_EXAMPLE`
names (see `docs/inputs.md`), and skip when it is not set or the files are missing.

## Licence

LGPL-3.0-only, see `LICENSE`.
