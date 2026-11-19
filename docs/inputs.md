# Inputs

The IP-XACT files the exporter reads, where they come from, and which step uses them.

The running example is the XactFlow author's `example_XactFlow`, an SoC called `soc_a`:
a CPU, an APB interconnect, a UART, a GPIO and a debug module.

Clone it anywhere and point `RTLGEN_EXAMPLE` at the clone. The tests read it from there (D3);
these docs write `$EX` for it:

```bash
git clone https://github.com/mtravaillard/example_XactFlow.git
export RTLGEN_EXAMPLE=$PWD/example_XactFlow
EX=$RTLGEN_EXAMPLE
```

Developed against commit `89b719f` (2026-11-12, "Add I/Os on example"). It has no licence
file, so none of its files, nor anything generated from them, goes into this repository: the
generated files live in `build/`, which git ignores.

## How they fit together

```
design.py ──archidesc importer──► IP-XACT XML ──xactflow rtl──► soc_a.sv
(Python)                          (the inputs)                  (the output)
```

The exporter never reads `design.py`, only the XML.

## Source files (in the example, used in place through `--lib`)

| File                                     | Kind                   | What it holds                           | Used in   |
|------------------------------------------|------------------------|-----------------------------------------|-----------|
| `$EX/xml_to_design/cpu.xml`              | component              | the CPU: ports, parameters, module name | steps 2-4 |
| `$EX/xml_to_design/uart.xml`             | component              | the UART                                | steps 2-4 |
| `$EX/xml_to_design/gpio.xml`             | component              | the GPIO                                | steps 2-4 |
| `$EX/xml_to_design/debug.xml`            | component              | the debug module                        | steps 2-4 |
| `$EX/xml_to_design/apb_interconnect.xml` | component              | the APB interconnect                    | steps 2-4 |
| `$EX/bus_definitions/apb4.xml`           | bus definition         | the APB bus                             | step 6    |
| `$EX/bus_definitions/apb4_rtl.xml`       | abstraction definition | APB's logical ports                     | step 6    |

They are not copied: a copy goes stale when the author updates the original, and two files
with the same VLNV in the library are an error (SCR 1.1).

## Generated files (in `build/soc_a/`)

| File                                         | What it holds                                                                | Used in    |
|----------------------------------------------|------------------------------------------------------------------------------|------------|
| `example.org_design_soc_a.design_1.0.xml`    | the design: instances and how they connect; the file given to `xactflow rtl` | steps 1-7  |
| `example.org_design_soc_a.component_1.0.xml` | the SoC seen as one IP: its own ports, and the view naming the module (D1)   | steps 1, 5 |

VLNVs: the design is `example.org:design:soc_a.design:1.0`, the component
`example.org:design:soc_a.component:1.0`. Linked with the source files, the design has
5 instances and 5 interconnections, with no errors.

Made with archidesc 0.3.1, from the example's folder, starting in this repository's root:

```bash
OUT=$PWD/build/soc_a
cd "$EX/xml_to_design"
xactflow archidesc design.py --then design    --output "$OUT"
xactflow archidesc design.py --then component --output "$OUT"
cd -
```

This runs the author's `design.py`. The output folder is created if missing. Rerun both
commands when the example changes.

## Traps

- `--lib` scans a folder and all its subfolders for `.xml` files. `$EX/xml_to_design/out/`
  holds an old design from an XactFlow 0.3.0 run, `example.org_design_soc_a_1.0.xml`, which is
  scanned too. It is harmless: its VLNV name is `soc_a`, not `soc_a.design`.
- Never write the generated files into `$EX/xml_to_design/out/` as well: two copies of
  `soc_a.design` in the library are a duplicate VLNV error (SCR 1.1).
- A design file under a `--lib` folder can also be the file given on the command line: the
  library reads each file once.
- archidesc 0.3.0 writes the component's view with no `componentInstantiationRef`, which D1
  refuses. Make the inputs with archidesc 0.3.1, as installed in `setup.md`.
