# rtlgen

A [XactFlow](https://github.com/IP-XACT/XactFlow) exporter plugin that generates a
SystemVerilog top-level module from an IEEE 1685-2022 (IP-XACT) design.

It is being written step by step. Steps 1 and 2 are done: the plugin is registered with
XactFlow as the `rtl` subcommand, links the design against its library, names the module from
the component that holds the design, and writes the module with one instance per
subcomponent, each named after the module its component gives. Ports, parameters and
connections come in the next steps.

## Use

```bash
pip install -e .
xactflow rtl <design.xml> --lib <dir> [--lib <dir> ...] --output <dir>
```

It writes `<module>.sv` into the output folder. It refuses, with a message, anything it does
not handle yet: options, design configurations, a design that does not link, a module name
it cannot find, a hierarchical or virtual subcomponent, or one in a language other than
SystemVerilog (see `docs/decisions.md`).

## Docs

- `docs/decisions.md`: the decisions that shape the exporter, why they were made, and what
  would reopen them.

## Tests

The tests read the XactFlow author's example design, `soc_a`, from the clone that
`RTLGEN_EXAMPLE` names, and skip when it is not set or the generated files are missing (D3).
The example has no licence file, so nothing from it, nor generated from it, goes into this
repository: the generated files live in `build/`, which git ignores.

```bash
pip install -e . pytest xactflow-archidesc==0.3.1 xactflow-design==0.2.1 xactflow-component==0.2.1
git clone https://github.com/mtravaillard/example_XactFlow.git ../example_XactFlow
export RTLGEN_EXAMPLE=$(realpath ../example_XactFlow)

# The design and the component holding it, into build/soc_a. Rerun when the example changes.
OUT=$PWD/build/soc_a
cd "$RTLGEN_EXAMPLE/xml_to_design"
xactflow archidesc design.py --then design    --output "$OUT"
xactflow archidesc design.py --then component --output "$OUT"
cd -

pytest -q
```

archidesc 0.3.0 writes a component that D1 refuses, so use 0.3.1.

## Licence

LGPL-3.0-only, see `LICENSE`.
