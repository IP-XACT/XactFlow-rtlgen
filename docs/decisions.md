# Decision log

What was decided, why, and what would reopen it. Newest last. A changed decision gets a new
entry, and the old one is marked superseded rather than edited.

---

## D1. Where the module name comes from
*2026-11-18 · active · item 5 superseded by D5 (2026-11-19)*

- **Decision:** the module name is the `moduleName` that the containing component gives through
  the view instantiating the exported design. Every case where that is missing or unclear is
  refused.
  1. Which view gives the module name: the view whose `designInstantiationRef` names a design
     instantiation whose `designRef` is the exported design, the same rule `link()` uses to find
     the containing component. Its `componentInstantiationRef` gives the `moduleName`.
  2. No containing component (`linked.component` is `None`): refused, with a message to add the
     component that holds the design to the library (with archidesc, the `--then component`
     output).
  3. The view has no `componentInstantiationRef`, the reference names no component
     instantiation, or the component instantiation has no `moduleName`: refused, with a message
     naming the component, the view and what is missing.
  4. Several views instantiate the design: accepted if they all give the same module name,
     refused if the names differ. Each matching view must give a name, as in 3.
  5. *Superseded by D5, which applies it to every name rtlgen writes.* The name is not a legal
     SystemVerilog identifier: a name not of the simple identifier form (a letter or `_`, then
     letters, digits, `_` or `$`; IEEE 1800 5.6) is refused. Keywords are not checked yet.
  6. The containing component has no view whose `designInstantiationRef` leads to the design (it
     holds the design through a design configuration instead, which `link()` also accepts):
     refused, as design configurations are.
- **Why:** the name must be one the input states, never a guess. A guessed name gives a module
  that nothing instantiates under that name, with no error from the exporter; a refusal is loud
  and can be loosened later. Following the same view as `link()` means the name comes from the
  view that made this component the container. It is also what the input's producer intends:
  archidesc 0.3.1 says the component "names the module that HDL is generated for" and writes
  both references in one view. The containing component is needed anyway for the top-level
  ports (step 5), so requiring it costs nothing.
- **Considered:**
  1. The first view: view order in the XML means nothing. A view with a fixed name (`rtl`,
     `hierarchical`): view names are free text and differ between tools.
  2. The design's VLNV name with `.design` stripped: fits archidesc and Kactus2 naming only, and
     when two components hold the design it hides the ambiguity. The VLNV name as it is:
     `soc_a.design` is not a legal SystemVerilog identifier.
  3. The component's VLNV name with `.component` stripped: fits archidesc naming only. The view's
     or the component instantiation's name: IP-XACT names, not module names (`hierarchical`,
     `hierarchical_rtl` in the example). The design's name with `.design` stripped: the guess
     already rejected in 2. archidesc 0.3.0 writes a view with no `componentInstantiationRef`;
     refusing tells its users to upgrade instead of giving them a made-up name.
  4. The first matching view: the result would depend on the order in the file. Refusing
     whenever more than one view matches: refuses a case that is not ambiguous. An option to
     pick the view, or one module per view: nothing needs them yet.
  5. An escaped identifier (`\soc.a `): legal, but every reference needs the same spelling and
     the file name gets the bad characters. Repairing the name (bad characters to `_`): a silent
     rename, and two names can collide. Checking keywords now: the list differs between
     versions of IEEE 1800, and a keyword fails loudly at compile time, not as wrong RTL.
  6. Following the design configuration to its design: design configurations are not supported
     yet (step 8).
- **Revisit if:**
  - XactFlow changes how `link()` finds the containing component (`_instantiates_design`,
    `link/resolver.py:62-89` in 0.4.0): the lookup here copies its rule, as that function is
    private, so check they still agree on each XactFlow upgrade.
  - Design configurations are supported (step 8): accept 6.
  - A real input has several views instantiating the design with different module names: add
    an option to pick the view (`--option view=<name>`).
  - A keyword as a name turns out to reach users: check against the keyword list of one IEEE 1800
    version (Annex B).
  - Step 2 needs the same check for instance names: move item 5 to an entry of its own, for every
    name the exporter writes. Done: D5.

## D2. Only files rtlgen wrote are overwritten
*2026-11-18 · active*

- **Decision:** every file the exporter writes starts with the line
  `// Generated by rtlgen from <design VLNV>. Do not edit.` An existing file is overwritten only
  if its first line starts with `// Generated by rtlgen`; any other existing file is refused,
  naming it. The output folder is created if it does not exist.
- **Why:** regenerating into the same folder must work, but `--output` pointed at a source
  folder must not silently destroy a hand-written `<module>.sv`. The header also tells anyone
  opening the file that it is generated, and from which design.
- **Considered:** always overwriting: simple, but loses hand-written files without a word.
  Never overwriting: every rerun would need the old file deleted first. An `overwrite` option:
  nothing needs it yet.
- **Revisit if:** the marker line changes (files with the old marker would then be refused), or
  a flow needs to replace files that rtlgen did not write.

## D3. The tests read the author's example
*2026-11-18 · active*

- **Decision:** the tests take their input from the author's example, read in place from the
  clone that `RTLGEN_EXAMPLE` names, and the files generated from it in `build/soc_a/`. Each
  refusal is the linked example changed inside the test, or a library scanned without part of
  it. A test skips, naming what is missing, when `RTLGEN_EXAMPLE` is not set or the example or
  the generated files are absent.
- **Why:** it is real input from the toolchain's author, and it needs no files in this
  repository: the example has no licence, so none of it may be copied here. The path comes only
  from the variable, so nothing in the repository depends on one machine's folders.
- **Considered:** small IP-XACT objects built in Python inside the tests: portable and ready for
  CI, but much more code, and not real input. Copies of the example's files: no licence. A
  default path to a local clone: no setup on one machine, but it ties the repository to it.
- **Revisit if:** the tests should run in CI: clone the example there and set `RTLGEN_EXAMPLE`,
  or build the inputs in Python, or use an input whose licence allows copying it.

## D4. Where an instance's module name comes from
*2026-11-19 · active*

- **Decision:** each instance is written as `<module> <instance name> ();`, in design order,
  where `<module>` is the `moduleName` that the instance's component gives through its view with
  a `componentInstantiationRef`. Every case where that is missing, unclear or not supported yet
  is refused.
  1. Which view gives the module name: each view with a `componentInstantiationRef`. A view with
     no reference at all (documentation, say) is ignored.
  2. A component with any view that has a `designInstantiationRef` or a
     `designConfigurationInstantiationRef` is hierarchical: refused until step 8, whichever view
     would give the name.
  3. The reference names no component instantiation, or the component instantiation has no
     `moduleName`: refused, as in D1 item 3, with a message naming the component, the instance
     and the view.
  4. No view has a `componentInstantiationRef`, or the component has no model: refused.
  5. Several views have one: accepted if they all give the same module name, refused if the
     names differ. Each must pass 3, 6 and 7.
  6. `language`: `systemverilog`, compared ignoring case and surrounding spaces, is accepted, and
     so is a missing or empty `language`. Any other language (`verilog`, `vhdl`, ...) is refused.
  7. `isVirtual` true: refused. IEEE 1685-2022 says such a component "shall not be netlisted",
     and what that means for its connections is not decided yet.
  8. The module name must be a legal identifier (D5).
- **Why:** as in D1, the name must be one the input states, never a guess, and a refusal can be
  loosened later. The view with a `componentInstantiationRef` is where IP-XACT puts the module,
  so the top (D1) and the instances follow one rule. Refusing hierarchical components leaves
  step 8 free to decide how sub-designs are generated, and costs nothing on the example, which
  has none. rtlgen considers only SystemVerilog input files and always writes SystemVerilog, so
  any other stated language is refused. `language` is optional in IEEE 1685-2022, so leaving it
  out is not refused. No input at hand sets `isVirtual`, so refusing it costs nothing either.
- **Considered:**
  1. The view named `rtl`: view names are free text, and the example's are `rtl_view`, so it
     would refuse the example. The first view: a silent guess when a component has several.
  2. Instantiating a hierarchical component by its `moduleName` and expecting its RTL from
     elsewhere (a separate rtlgen run): a missing module would fail loudly at build time, but
     it fixes how step 8 works before step 8.
  6. Accepting `verilog` as well: rtlgen is SystemVerilog only. Refusing a missing `language`:
     chosen first, then dropped the same day: the element is optional, and Croc leaves it out on
     all 20 of its component instantiations. Not checking `language`: a VHDL leaf would be
     written as SystemVerilog and found only when the build fails.
  7. Leaving a virtual instance out, as the standard says: from step 4 on, connections to it
     would point at nothing. Ignoring `isVirtual`: wrong RTL with no error.
- **Revisit if:**
  - Hierarchy is supported (step 8): accept 2.
  - Real SoCs (step 9): Didactic writes `Verilog` on its 30 component instantiations, so 6
    refuses Didactic. Decide again then.
  - A real input sets `isVirtual`: decide what a virtual instance means for its connections (7).
  - A real input has a component whose views give different module names: an option to pick the
    view, or the view a design configuration chooses (step 8).

## D5. Every name rtlgen writes is a simple identifier
*2026-11-19 · active · names added for step 4 (2026-11-24), 5 (2026-11-25) and 6 (2026-11-26)*

- **Decision:** every name the exporter writes into SystemVerilog must be a simple identifier: a
  letter or `_`, then letters, digits, `_` or `$` (IEEE 1800 5.6). Any other name is refused,
  with a message saying which name it is and where it comes from. Keywords are not checked yet.
  This replaces D1 item 5. From step 2 it covers the module name (D1), each instance's module
  name (D4) and each instance name; from step 3 each module parameter name (D6); from step 4
  each ad hoc connection name, which names its net (D9), and each port name in an instance's
  port list (D10); from step 5 each top port name in the module header (D14); from step 6 each
  bus net name (D18) and each physical port in a port map (D20). Later steps add their names
  here, not a rule of their own.
- **Why:** one rule in one place: a new kind of name needs no new decision, and copies of a rule
  cannot drift apart. The reasons against escaped identifiers, repairing names and checking
  keywords are those of D1 (considered, 5).
- **Considered:** the rule repeated in each decision (D1 item 5, then a copy in D4, and one in
  every later step): the same text many times over.
- **Revisit if:** a keyword as a name turns out to reach users: check against the keyword list of
  one IEEE 1800 version (Annex B).

## D6. Which module parameters are written
*2026-11-19 · active*

- **Decision:** an instance whose component instantiation (D4) has module parameters is written
  as `<module> #( ... ) <instance name> ();`, with one `.<name>(<value>)` per line for every
  module parameter, in the instantiation's order, each with its value in this design (D7).
  What rtlgen cannot write correctly is refused.
  1. Which module parameters: all of them, overridden or not. An instantiation with none is
     written as in D4, without `#( ... )`.
  2. Overrides: each `configurableElementValue` the design gives the instance replaces the value
     of the component parameter its `referenceId` names, and only the value: the parameter's
     limits stay. An override naming no parameter of the component is refused. That also
     refuses an override naming a module parameter directly, which SCR 5.3 forbids.
  3. An override of a parameter with `resolve="immediate"` is applied, not refused: SCR 5.28 is
     XactFlow's to check.
  4. Several views that D4 accepts: their instantiations must give the same parameter lines,
     compared once the values are worked out, or they are refused.
  5. `usageType`: only `typed` maps to a SystemVerilog module parameter (IEEE 1685-2022
     Tables 4 and 5). `nontyped` and `runtime` are refused for now. A missing `usageType` is
     `typed`, the schema's default and what ipxact-compiler gives.
  6. Names: each module parameter name must be a legal identifier (D5). A name given twice in
     one instantiation is refused (IEEE 1685-2022 6.15.6.2 b); SystemVerilog does not allow a
     parameter connected twice either.
  7. Limits and choices: rtlgen adds no checks of its own. The Semantic Consistency Rules are
     XactFlow's to implement. The evaluator's own minimum and maximum check, for number types
     only, still runs on every value rtlgen works out (D7).
- **Why:** a module parameter that is not overridden still configures the module, and the
  component's value for it may differ from the default in the RTL, so every one is written.
  rtlgen refuses only what it cannot write correctly: a check that would not change the output
  belongs in XactFlow, where every exporter gets it. The standard does not say which module
  parameters an exporter writes; 6.15.6.2 calls a module parameter "a name-value pair used to
  configure the model of this component instance".
- **Considered:**
  1. Writing only the overridden module parameters: a bet that every value in the component
     equals the default in the RTL.
  3. Refusing an override of an immediate parameter: a check that changes nothing in the
     output.
  4. Picking one of the views when their parameters differ: a silent guess, as in D4 item 5.
  5. Reading a missing `usageType` as `nontyped`, as one reading of the standard's text does:
     the schema says `typed`.
  7. Checking `minimum`, `maximum` and `choices` in rtlgen: a second copy of XactFlow's rules.
- **Revisit if:**
  - ipxact-compiler keeps both of an override given twice: today it keeps one, so rtlgen
    cannot see the duplicate.
  - A real input uses `nontyped` or `runtime` (5), or overrides a module parameter directly, as
    the example in IEEE 1685-2022 C.6 does despite SCR 5.3 (2).
  - XactFlow checks overrides against the component itself: the check in 2 can go.

## D7. How a module parameter's value is written
*2026-11-19 · active*

- **Decision:** a value that refers to no parameter is written exactly as the XML has it. A
  value that refers to a parameter is worked out by XactFlow's evaluator and written as a plain
  decimal number.
  1. Refers to no parameter: once strings, based literals (`8'hA5`, `'1`), numbers (`1e5`) and
     `$` functions (`$clog2`) are set aside, no name is left. Written as it stands, with
     surrounding spaces trimmed: `"fast"`, `8'hA5`, `1e5`, `$clog2(256)`.
  2. Refers to a parameter: a bare name (`BAUDRATE`) or an expression with one (`BAUDRATE*2`,
     `$clog2(BAUDRATE)`). Worked out with `xactflow.evaluate()` and written in decimal: `9600`,
     `19200`, `14`.
  3. A name can only mean a parameter of the instance's own component, with the design's
     overrides in place (D6 item 2). The design's parameters are refused (D8). The component's
     instantiation parameters, and module parameters with a `parameterId`, are not reached.
  4. A parameter with no `type` (the schema's default is `string`) or `type="string"`, whose
     value is a number, is used as that number, as XactFlow's evaluator does. A real string
     reached through a parameter is refused.
  5. A value the evaluator cannot work out (an unknown name, a syntax error, a string, an array,
     `$ipxact_*`, a circular reference, a value outside its limits) is refused, with a message
     naming the instance, the module parameter, its text and the evaluator's reason.
- **Why:** the component's parameters are not names in the generated module, so a value that
  refers to one cannot be copied into the SystemVerilog: it has to be worked out. XactFlow's
  evaluator is the one all exporters share, so rtlgen gets its fixes and has no evaluator of its
  own. Its public `evaluate()` returns only the number, with no width, so plain decimal is what
  rtlgen can write. A value with no parameter in it is kept as written: copying it cannot be
  wrong, and working it out could lose what the author wrote, such as a width or a base.
- **Considered:**
  2. Writing every value as the XML has it, following only bare names and refusing every
     computed value (`BAUDRATE*2`): no evaluator. Chosen first, then replaced the same day.
     Writing a worked-out number with a width (`32'd19200`): `evaluate()` gives no width.
  4. Reading a parameter with no `type` as a string, as the schema's default says: the
     example's parameters have no `type`, so the UART would be refused.
- **Revisit if:**
  - Real SoCs (step 9) have derived values that the evaluator works out differently from
    SystemVerilog: its width and sign rules are simpler.
  - An untyped RTL parameter (`parameter P = 8'hFF`) takes its width from the value it is given:
    a plain decimal changes that width.
  - The evaluator gives widths, strings or arrays.
  - A syntax error in an override is reported with the module parameter's text, not the
    override's: give the override's text when that misleads.

## D8. The top's own parameters wait for step 8
*2026-11-19 · active*

- **Decision:** the generated module has no parameters of its own. A top that has any is
  refused until step 8.
  1. The design has `<parameters>`: refused.
  2. A component instantiation that D1 takes the module name from has module parameters:
     refused.
  3. The containing component's own `<parameters>` are accepted: nothing is written from them,
     and with 1 refused, no value can reach them (D7 item 3).
- **Why:** writing `module <name> #(parameter ...)` means deciding how a parameter is declared
  (its type and default), and whether an instance's value that refers to a top parameter is
  written as that name or worked out (D7). Both belong to hierarchy (step 8), where a generated
  module is itself instantiated with values. Without the refusal, a value that refers to a
  design parameter would be worked out against the instance's component only, and could
  silently find a parameter of the same name there. The example has none of these, so the
  refusal costs nothing.
- **Considered:** writing the top's parameters now, as declarations: decides step 8 before
  step 8, and reopens D7.
- **Revisit if:** hierarchy is supported (step 8).

## D9. One wire per ad hoc connection, named after it
*2026-11-24 · active · items 2 and 4 extended to top ports by D15 and D16 (2026-11-25)*

- **Decision:** each ad hoc connection between instances becomes one net, named after the
  connection, and each of its ports is connected to it.
  1. Form: `wire <name>;` for one bit, `wire [W-1:0] <name>;` wider (D12), one per line, in
     design order, before the instances and followed by a blank line. Each port of the
     connection is written `.<port>(<name>)` in its instance's port list (D10).
  2. Connections that share a port (the same port of the same instance, directly or through
     other connections) are one net, named after the first of them in design order. A port
     listed twice is written once.
  3. Every net is a `wire`, so any mix of directions is accepted, several drivers and inouts
     included.
  4. Names: the connection name must be a legal identifier (D5). A net with the same name as an
     instance is refused. Two connections with the same name are refused: IEEE 1685-2022 7.5.2
     requires the names to be unique.
- **Why:** the connection's name is what the author wrote, so the RTL reads like the design.
  Merging: IEEE 1685-2022 does not say what a port in two ad hoc connections means. 7.5.2 asks
  only for unique names and at least one port reference, 7.6.2 calls a connection's port
  references "the full set of pins and ports involved in a single ad-hoc connection", and no
  Semantic Consistency Rule covers it. But archidesc writes one connection per `connect()`
  call, so a driver wired to several inputs is one port in several connections: the example
  does this for `clk_i` and `rst_ni`. A SystemVerilog port takes one expression, so the
  connections can only be one net. `wire`: slang refuses two drivers on a `logic` ("cannot have
  multiple continuous assignments to variable") and an inout on one ("only nets are allowed");
  both are legal on a `wire`. Names: a net and an instance share the module's namespace
  (Verilator: "Instance has the same name as variable"; slang: "redefinition"). `xactflow link`
  0.4.1 keeps only the last of two connections with one name, with no diagnostic, so rtlgen
  reads the names from the design as written.
- **Considered:**
  1. A net named after its driver, `<instance>_<port>`: an invented name, it needs exactly one
     driver, and it clashes with the example's top port `uart_tx_o`. A net per port and an
     `assign` per connection, as the old exporter did: more lines, and net names the design
     does not have. The cost accepted: bit ranges (step 7) become concatenations in port
     lists.
  2. Refusing a port in two connections: chosen first, then replaced the same day, once
     archidesc's fan-out showed it would refuse ordinary designs.
  3. Refusing several drivers and inouts on a net: both are legal on a `wire`, so it would
     refuse designs that SystemVerilog accepts. A `wire` only for nets with several drivers or
     an inout, `logic` elsewhere: a rule about directions for no gain in the output.
  4. Renaming a net that clashes with an instance (adding `_net`, as the old exporter did):
     an invented name, which can clash again.
- **Revisit if:**
  - Top-level ports (step 5): connections that share only a top port (the example's `clk_i` is
    in five) must become one net through it. Done: D15.
  - Bit ranges (step 7): one port in several connections with different bits is the normal case
    there, so merging by whole port no longer fits.
  - The IEEE 1685 working group says what a port in two ad hoc connections means.
  - `xactflow link` reports duplicate connection names.

## D10. Ports in the component's order
*2026-11-24 · active*

- **Decision:** an instance with connected ports is written `<module> <instance name> ( ... );`,
  with one `.<port>(<net>)` per line, four spaces deep, in the order of its component's ports
  (`model.ports`). Only connected ports are listed. Each port name must be a legal identifier
  (D5).
- **Why:** the order then matches the module's own port list, so the two can be read side by
  side, and it does not change when the design lists its connections in another order.
- **Considered:** the order of the connections in the design: the port list would follow how
  the design happens to be written.
- **Revisit if:** unconnected ports (step 7) are written too.

## D11. Connections to top ports wait for step 5
*2026-11-24 · superseded by D15 (2026-11-25)*

- **Decision:** an ad hoc connection with an `externalPortReference` is left out, with no
  message, until step 5. So is every connection merged with it (D9 item 2). The instance ports
  it would connect are left out of their port lists.
- **Why:** top-level ports are step 5. 20 of the example's 22 ad hoc connections reach a top
  port (`clk_i`, `rst_ni`, the UART, GPIO and JTAG pins), so refusing would refuse it. The
  generated module has no ports yet, so the missing connections are plain to see, not hidden.
- **Considered:** refusing such connections: refuses the example until step 5. Writing the
  instance side as a net of its own: a net that goes nowhere.
- **Revisit if:** top-level ports are written (step 5). Done: D15.

## D12. Ports on a net have the same width and bit order
*2026-11-24 · active · extended to top ports by D16 (2026-11-25), to bus nets by D19 (2026-11-26)*

- **Decision:** all ports on a net must have the same width and the same bit order. The net is
  declared `[W-1:0]`, or with no range for one bit.
  1. Bounds are worked out for each instance with `xactflow.evaluate()`, with the design's
     overrides in place: `[BAUDRATE/1200-1:0]` with `BAUDRATE` 9600 is 8 bits.
  2. Bounds that differ but give the same width (`[15:8]` and `[7:0]`) are accepted:
     SystemVerilog connects them bit by bit, left to right.
  3. Different widths are refused: part selects wait for step 7.
  4. Opposite bit orders (`[7:0]` with `[0:7]`) are refused.
  5. A port with several vectors, or a bound that cannot be worked out, is refused, naming it.
- **Why:** SystemVerilog pads or cuts a port connected to a net of another width, with at most
  a lint warning, so a width mismatch would give wrong RTL with no error from rtlgen. With
  opposite bit orders, SystemVerilog joins bit 7 of one port to bit 0 of the other; whether
  that is what IEEE 1685 means was not checked, so it is refused rather than guessed.
- **Considered:** accepting opposite bit orders, connected left to right as SystemVerilog does:
  a guess about the standard.
- **Revisit if:** part selects are supported (step 7), or the standard's bit mapping for
  opposite orders is checked.

## D13. What rtlgen cannot wire yet is refused
*2026-11-24 · active · extended to top ports by D17 (2026-11-25), to buses by D20 (2026-11-26)*

- **Decision:** an ad hoc connection with any of these is refused, with a message naming the
  connection and, for 1 to 5, the port and its instance:
  1. a `phantom` port: it is not in the module, so there is nothing to connect;
  2. a port that is not a wire port (transactional or structured);
  3. a port with array dimensions (`<arrays>`);
  4. a `partSelect`;
  5. a `subPortReference`;
  6. a `tiedValue`.
- **Why:** before these checks, rtlgen ignored 3 to 6 and wrote wrong RTL with no error: a tie
  lost, a whole port wired where only part of it was meant; 2 crashed. rtlgen refuses what it
  cannot write correctly instead of writing something wrong. Tie-offs and bit ranges are
  step 7.
- **Considered:** leaving a phantom port out of its net with no message: the connection would
  lose an end silently.
- **Revisit if:** tie-offs and bit ranges are supported (step 7: 4 and 6), or a real input
  (step 9) has structured, transactional or array ports, or sub-ports.

## D14. The module's ports are the containing component's
*2026-11-25 · active*

- **Decision:** the module declares every port of the containing component (D1), connected or
  not, in the component's order (`model.ports`).
  1. Form: an ANSI header, one port per line, two spaces deep: `<direction> wire <range> <name>`,
     such as `input wire [15:0] gpio_i`, with no range for one bit. `in`, `out` and `inout`
     give `input`, `output` and `inout`.
  2. Range: the component's own bounds, worked out with its parameters and written as they
     come: `[16:1]` stays `[16:1]` and `[0:7]` stays `[0:7]`.
  3. A phantom port is not in the module, so it is left out.
  4. A component with no ports, or only phantom ones, gives `module <name>;`, as before step 5.
  5. Each name must be a legal identifier (D5). D16 and D17 hold the checks.
- **Why:** the component is how the rest of the world sees the module. A parent design (step 8)
  or a hand-written top wires the component's ports, and the ports that bus interfaces reach
  (step 6) come through port maps, not `externalPortReference`s. Taking only the ports a
  connection reaches would drop those without a word, and the port list would change whenever
  a connection inside changed. `wire` for the reasons of D9: several drivers and `inout` are
  legal on it, and it does not depend on `` `default_nettype ``. The component's own bounds keep
  bit 1 of the IP-XACT bit 1 of the RTL. A phantom port is, by IEEE 1685, in the IP-XACT but not
  in the HDL. In the example: 12 ports, 8 inputs and 4 outputs, all 1 bit or `[15:0]`.
- **Considered:**
  1. Only the ports an `externalPortReference` reaches: drops spare pins and bus-interface ports
     silently, and the module no longer matches its component.
  2. An ANSI header with no type (`input [15:0] gpio_i`): fails under
     `` `default_nettype none ``. The non-ANSI style, names in the header and declarations in
     the body: twice the lines, for nothing in SystemVerilog.
  3. Every range as `[W-1:0]`, as D12 does for nets: `[16:1]` would become `[15:0]`, and the bit
     numbers would no longer match the component's. The bounds as expressions
     (`[DATA_W-1:0]`): needs the top's own parameters, which D8 refuses.
  4. Refusing a component with a phantom port: refuses a valid component. Writing a net that
     reaches a phantom top port as an internal wire: a guess at what the standard means.
  5. Always `module <name> ();`: the `()` adds nothing.
- **Revisit if:**
  - Bus interfaces (step 6): their ports are already declared here; D16's "reached" must count
    them. Done: no change yet, as D20 item 2 refuses `hierInterface`s until step 8.
  - The top's own parameters are supported (step 8): bounds may then be written as expressions.
  - A real input (step 9) uses phantom top ports, for example to pass a bus interface through.

## D15. A connection to a top port is wired to the port
*2026-11-25 · active · supersedes D11*

- **Decision:** a net that reaches a top port is that port: its instance ports are written
  `.<port>(<top port>)`, and no `wire` is declared for it, as the module header declares it
  (D14).
  1. Connections that share a top port are one net, as connections that share an instance's
     port are (D9 item 2): `clk_i`'s five connections in the example are one net.
  2. The net takes the top port's name. Its connections' names are not written, so they are not
     checked (D5).
  3. A net that reaches two different top ports (a pass-through) is refused, naming the ports.
- **Why:** this is how a hand-written top reads. Merging on the top port is needed because
  archidesc writes one connection per `connect()` call, so the clock reaches five instances
  through five connections. It also matters for the checks: a top output can be driven through
  one connection and read through another, and only the whole net shows the driver (D16). With
  two top ports, the net would need two names: an `assign` needs a direction, so it cannot join
  two inputs, two outputs or an `inout`, and `alias` (IEEE 1800 10.11) is not taken by Yosys and
  only partly by Verilator. The example has no pass-through, so the choice waits for one.
- **Considered:**
  1. One `wire` per connection, named after it, and an `assign` to the top port: five wires and
     five `assign`s for one clock, and no way to write an `inout`.
  2. For two top ports: `assign <output> = <input>;`, or `alias`, as above.
- **Revisit if:** a real input (step 9) has a pass-through between top ports; bit ranges (step 7)
  make merging by whole port wrong, as for D9.

## D16. Checks at top ports
*2026-11-25 · active · item 1 extended to bus nets by D19 (2026-11-26)*

- **Decision:** on top of D14 and D15:
  1. Names: a top port with the same name as an instance is refused, and so is a net named
     after its connection (D9) with the same name as a top port. A phantom top port is not in
     the module, so it clashes with nothing.
  2. Widths: D12's rule, with the top port counted as one more port on its net. Same width and
     bit order are needed; `[16:1]` on the top port against `[15:0]` on an instance is accepted.
  3. Directions, on the whole net (D15 item 1):
     - an instance output on the net of a top input is refused;
     - a top output with no instance output or `inout` on its net is refused, and so is a top
       output that no connection reaches;
     - a top `inout`, and an instance `inout` on a top input, are accepted.
  4. A top input or `inout` that no connection reaches is accepted: it is declared and not used.
- **Why:** names: ports, nets and instances share the module's namespace. For a top port named
  like an instance, Verilator stops with "Non-interface used as an interface" and slang only
  warns ("redefinition"), so the file could get through one tool. Widths: SystemVerilog pads or
  cuts silently, as in D12. Directions: an instance output on a top input drives a net that is
  driven from outside the module; Verilator stops with `ASSIGNIN` and slang says nothing. An
  undriven top output floats at `z`, with only an `UNDRIVEN` warning from Verilator `-Wall` and
  nothing from slang: wrong RTL with no error. Writing it correctly needs a value, from a
  `tiedValue` or the port's `<drivers>`, which waits for step 7, so it is refused rather than
  guessed. An unused input needs no value: the module ignores the pin, as the design says, with
  only `UNUSEDSIGNAL` from Verilator `-Wall`. Spare pins and test inputs are common in real tops.
- **Considered:**
  1. Renaming a net that clashes (adding `_net`): rejected in D9 for the same reasons.
  2. Requiring the top port's bounds to match exactly: refuses `[16:1]` against `[15:0]`, which
     SystemVerilog connects correctly.
  3. Any mix of directions, as on internal nets (D9 item 3): a driven input then fails later in
     Verilator, and an undriven output passes silently. Refusing only the driven input: an
     undriven output passes silently.
  4. Refusing an unreached input: refuses designs with spare pins, though nothing wrong is
     written.
- **Revisit if:**
  - Bus interfaces (step 6): ports reached through a hierarchical interconnection count as
    reached, and their drivers as drivers. Done: no change yet, as D20 item 2 refuses
    `hierInterface`s until step 8.
  - Tie-offs and default drivers (step 7): an undriven output with a `tiedValue` or a
    `<drivers>` default can be written.

## D17. What rtlgen cannot write at a top port is refused
*2026-11-25 · active*

- **Decision:** the refusals of D13, for the top-port end:
  1. When declaring any top port, connected or not (D14): a port that is not a wire port, one
     with `<arrays>`, or one with several vectors.
  2. At an `externalPortReference`: a phantom top port (D14 item 3), a non-wire port, a
     `partSelect` or a `subPortReference`. Each message names the connection and the port.
  3. A `tiedValue` on any connection of a net that reaches a top port: D13 item 6 now covers
     these connections, since D11's skip is gone.
- **Why:** without 2, a `partSelect` or `subPortReference` on the top-port end would be ignored
  and the whole port wired: wrong RTL with no error. 1 is needed because D14 declares every
  port, so one rtlgen cannot write would otherwise reach the header.
- **Considered:** skipping an unsupported top port that nothing connects instead of refusing
  it: drops a port from the module silently, against D14.
- **Revisit if:** part selects and tie-offs are supported (step 7), or a real input (step 9) has
  structured, transactional or array top ports.

## D18. One wire per logical port of a bus interconnection
*2026-11-26 · active*

- **Decision:** an interconnection between two instances' bus interfaces becomes one net for
  each logical port that both ends map, and each end's physical port is connected to it.
  1. Name: `<interconnection>_<logical port>`, both as written in the XML: `cpu_to_bus_PADDR`.
     D19 item 4 holds the name checks.
  2. Form: a `wire`, as in D9 item 1, with the width of D12 (D19 item 2). Each physical port is
     written `.<port>(<net>)` in its instance's port list, in the component's order (D10).
  3. Place: after the ad hoc wires, grouped by interconnection in design order. Each group
     starts with a blank line and `// <interconnection>`, and its wires follow the port-map
     order of the interconnection's first end.
  4. The port maps come from the bus interface's one `abstractionType` (D20 item 3).
- **Why:** a hand-written top wires a bus the same way: one signal per logical port, each port
  connected straight to it, as for ad hoc nets, with no `assign`. The name is unique in the
  module as long as interconnection names are (D19 item 4), and it leads back to the XML
  element. The comment does the same for each group: the example adds 50 bus wires
  (5 interconnections, 10 logical ports each), and a flat block of 50 lines is hard to scan.
  In the example the module then has 52 wires, every APB port is connected, and Verilator
  `-Wall` gives no warning on `soc_a.sv`.
- **Considered:**
  1. A net for each physical port, joined by an `assign`: two names and an `assign` per logical
     port, and no way to write an `inout`.
  2. Names in lower case (`cpu_to_bus_paddr`): reads like usual RTL, but two logical ports that
     differ only in case would share a name. The initiator's port name (`paddr_o`): two
     instances of one component have the same port names, so their nets would clash.
  3. One flat block of wires with no comments: hard to scan. Wires sorted by name: mixes ad hoc
     and bus wires and loses the design's order.
- **Revisit if:** broadcast, `hierInterface` or monitor interconnections are supported (D20),
  or bit ranges (step 7) map parts of logical ports.

## D19. Checks on bus nets
*2026-11-26 · active · extends D12 and D16 item 1 to bus nets*

- **Decision:** on top of D18:
  1. Both ends map the same logical ports: a logical port that one end maps and the other does
     not is refused, naming the interconnection, the logical port and the end that lacks it.
  2. Widths: D12's rule on the two physical ports, each worked out with its own instance's
     parameters. The abstraction definition's width is not checked.
  3. Directions: one `out` and one `in`, or an `inout` on either side. Two inputs (nothing
     drives the net) and two outputs (two drivers) are refused.
  4. Names: each net name must be a legal identifier (D5). A net with the same name as a top
     port that is not phantom, an instance, an ad hoc net or another bus net is refused, and so
     are two interconnections with the same name.
  5. A port that is on a bus net and in an ad hoc connection is refused, naming the port, the
     bus net and the connection. A port of a bus interface that no interconnection uses can
     still be wired ad hoc.
- **Why:**
  1. Leaving the mapped port open can leave an input undriven with no error, and driving it from
     the abstraction definition's default value is a tie-off (step 7). Before this check,
     rtlgen read only the first end's port maps, so a logical port that only the second end
     mapped was dropped without a word.
  2. SystemVerilog pads or cuts silently, as in D12. With no `logicalRange` or `partSelect`
     (D20 item 4), two ports of one width carry the logical port bit for bit, so checking them
     against the abstraction definition adds nothing to the RTL: it would validate the XML,
     which is not the exporter's job.
  3. A bus net has exactly two ends, so two inputs always float and two outputs always fight,
     unlike the ad hoc nets of D9 item 3, where other ports may drive the net. The modes are
     checked in D20 item 2.
  4. Ports, nets and instances share the module's namespace (D16). xactflow's `link()` does not
     report two interconnections with one name; their nets would clash with a message naming
     the same interconnection twice.
  5. Each instance port is connected once, `.<port>(<net>)`, so one of the two would have to
     win, or the nets would have to merge. Before this check, the bus net won silently.
- **Considered:**
  1. Leaving the port open; driving it from the abstraction definition's default value.
  2. Checking each port against the abstraction definition's width: needs the abstraction
     definition loaded and its width worked out for each mode. Sizing the net to the narrower
     port: SystemVerilog pads or cuts (D12).
  3. Any mix of directions, as on ad hoc nets: an undriven or doubly driven net passes
     silently. Checking each direction against the abstraction definition's direction for its
     mode: needs the abstraction definition, and on a two-end net it rarely catches more.
  5. Merging the bus net and the ad hoc net: a bus net could then have more than two ports and
     reach a top port, which needs new rules for its name (D18) and its directions (item 3).
     Letting one of them win silently: drops a connection the design asks for.
- **Revisit if:** tie-offs and default values are supported (step 7: item 1), part selects
  (step 7: item 2), or a real input (step 9) wires a bus port ad hoc as well (item 5).

## D20. What rtlgen cannot wire on a bus yet is refused
*2026-11-26 · active · extends D13 to bus interconnections*

- **Decision:** refused, with a message saying where it sits:
  1. In the design: a `monitorInterconnection`.
  2. In an interconnection: a `hierInterface` (a bus interface of the top); more than two
     active interfaces, even when the bus definition allows broadcast; any pair of modes other
     than an initiator with a target (mirrored, system and monitor modes, two initiators).
  3. At each end: a bus interface with no `abstractionType` or with several; `excludePorts`.
  4. In each port map: `isInformative`, `logicalTieOff`, `invert`, `logicalRange`, `partSelect`,
     a `subPortReference`; a logical port mapped twice, or a physical port mapped twice; a
     physical port the component does not have (SCR 2.19, which xactflow does not check); a
     physical port whose name is not an identifier (D5), that is not a wire port, that is
     phantom, or that has `<arrays>`, as D13 refuses for ad hoc connections.
- **Why:** each needs a rule the example does not exercise, and ignoring it would write wrong RTL
  with no error. Ignoring `excludePorts` or `isInformative` wires ports the design leaves out;
  ignoring `invert` drops the inversion; ignoring `logicalTieOff` loses the tie; a port mapped
  twice keeps only its last map. Several `abstractionType`s are one per view, and picking one
  needs views (step 8). A `hierInterface` is hierarchy (step 8): until then D14 and D16 stay as
  they are, so a top output that only a top bus interface would reach is refused as unreached.
  Broadcast: SCR 2.17 allows more than two ends only on a broadcast bus, and what the targets
  drive back would have several drivers, which D19 item 3 refuses. Modes: IEEE 1685 also allows
  an initiator with a mirrored initiator, a target with a mirrored target and a system with a
  mirrored system (SCR 2.4 to 2.9); the example has only initiators with targets.
- **Considered:**
  1. Handling `isInformative` and `excludePorts` now by leaving those logical ports out: the
     physical ports they leave open hit D19 item 1 or wait for step 7 anyway.
  2. Broadcast nets, one net per logical port joining every end: needs a direction rule for
     what the targets drive back.
  3. `hierInterface`s now, each instance port wired straight to the top port as in D15: needs
     the top's port maps and the rules for hierarchical modes, with no example to test them.
- **Revisit if:** tie-offs and bit ranges are supported (step 7: `logicalTieOff`,
  `logicalRange`, `partSelect`, `isInformative`, `excludePorts`), hierarchy and views (step 8:
  `hierInterface`, several `abstractionType`s), or a real input (step 9) uses mirrored or system
  modes, broadcast, `invert` or monitor interconnections.
