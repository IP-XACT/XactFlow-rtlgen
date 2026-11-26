# rtlgen

A [XactFlow](https://github.com/IP-XACT/XactFlow) exporter plugin that generates a
SystemVerilog top-level module from an IEEE 1685-2022 (IP-XACT) design.

It is being written step by step. Steps 1 to 6 are done: the plugin is registered with
XactFlow as the `rtl` subcommand, links the design against its library, names the module from
the component that holds the design, and writes the module with that component's ports and
one instance per subcomponent, each named after the module its component gives, with its
module parameters and their values in this design. Instances are wired to each other and to
the top ports through the design's ad hoc connections: one `wire` per net between instances,
and a net that reaches a top port is that port. Bus interconnections between two instances
are wired too: one `wire` per logical port that both ends map, named
`<interconnection>_<logical port>`. Unconnected ports, tie-offs and bit ranges come in the next
step.

## Use

```bash
pip install -e .
xactflow rtl <design.xml> --lib <dir> [--lib <dir> ...] --output <dir>
```

It writes `<module>.sv` into the output folder. It refuses, with a message, anything it does
not handle yet (see `docs/decisions.md`):

- options, design configurations, a design that does not link, a module name it cannot find;
- a hierarchical or virtual subcomponent, one in a language other than SystemVerilog, an
  override naming no parameter of the component, a module parameter that is not typed or
  whose value cannot be worked out, parameters on the top itself;
- a top port it cannot declare: a non-wire or array port, one with several vectors, or one
  named like an instance;
- an ad hoc connection it cannot wire yet: ports of different widths or bit orders, a phantom,
  array or non-wire port, a part select, a sub-port, a tie-off, a net that joins two top
  ports, an instance output driving a top input, a top output nothing drives, or a connection
  name that clashes with an instance or a top port or is used twice;
- a bus interconnection it cannot wire yet: a monitor interconnection, a top bus interface
  (`hierInterface`), more than two ends, modes other than an initiator with a target, no or
  several abstraction types, excluded ports, a port map that is informative, tied off,
  inverted, partial or to a sub-port, a logical port mapped by one end only or twice, a
  physical port mapped twice, missing, phantom, an array or not a wire, ports of different
  widths or bit orders, two inputs or two outputs on one net, a net name that clashes, an
  interconnection name used twice, or a port on both a bus net and an ad hoc connection.

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
