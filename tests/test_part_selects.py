"""Step 7d: part selects at the instance ends of ad hoc connections. Most cases widen cpu.irq_i
to 8 bits and feed it from two connections: IRQ from uart.irq_o, and DEBUG, moved from
cpu.debug_req_i (which is removed) to cpu.irq_i, from debug.debug_req_o."""
import copy
import dataclasses
import re

import ipxact
import pytest

from conftest import EXPECTED_SOC_A
from rtlgen import RtlExporter, _ad_hoc_nets, _instance_lines, _port_connections

IRQ = "uart_irq_o_to_cpu_irq_i"
DEBUG = "debug_debug_req_o_to_cpu_debug_req_i"
TX = "uart_tx_o_to_uart_tx_o"


def _port(linked, instance, port_name):
	"""A port of an instance's component."""
	return next(p for p in linked.instances[instance].component.model.ports if p.name == port_name)


def _set_range(linked, instance, port_name, left, right):
	"""Give a port of an instance's component the range [left:right]."""
	_port(linked, instance, port_name).wire.vectors = [
		ipxact.Vector(left=ipxact.Expression(value=left), right=ipxact.Expression(value=right))
	]


def _reference(linked, connection, port_name):
	"""The reference to a port in an ad hoc connection."""
	return next(r for r in linked.ad_hoc_connections[connection] if r.port.name == port_name)


def _select(reference, left, right):
	"""Make a port reference select [left:right] of its port."""
	reference.source.part_select = ipxact.PartSelect(
		range=ipxact.Range(left=ipxact.Expression(value=left), right=ipxact.Expression(value=right))
	)


def _move_debug_to_irq_i(linked):
	"""Point DEBUG's reference to cpu.debug_req_i at cpu.irq_i instead, and remove
	cpu.debug_req_i, which would be an open input (step 7a)."""
	references = linked.ad_hoc_connections[DEBUG]
	index = next(i for i, r in enumerate(references) if r.port.name == "debug_req_i")
	references[index] = dataclasses.replace(
		references[index],
		port=_port(linked, "cpu", "irq_i"),
		source=copy.deepcopy(references[index].source),
	)
	ports = linked.instances["cpu"].component.model.ports
	ports[:] = [port for port in ports if port.name != "debug_req_i"]


def _split(linked, cpu=("7", "0"), high=("7", "4"), low=("3", "0"), sources=("3", "0")):
	"""cpu.irq_i with range cpu, its bits high from uart.irq_o (IRQ) and low from
	debug.debug_req_o (DEBUG), both with range sources."""
	_set_range(linked, "cpu", "irq_i", *cpu)
	_set_range(linked, "uart", "irq_o", *sources)
	_set_range(linked, "debug", "debug_req_o", *sources)
	_select(_reference(linked, IRQ, "irq_i"), *high)
	_move_debug_to_irq_i(linked)
	_select(_reference(linked, DEBUG, "irq_i"), *low)


def _tie(linked, connection, value, *keep):
	"""Tie an ad hoc connection to value, keeping only the port references named in keep."""
	next(a for a in linked.design.ad_hoc_connections if a.name == connection).tied_value = (
		ipxact.Expression(value=value)
	)
	references = linked.ad_hoc_connections[connection]
	references[:] = [r for r in references if r.port.name in keep]


# Decision 1: a port connected in parts is a concatenation of the nets, from its left bit.

def test_port_in_parts_is_a_concatenation_from_its_left_bit(linked):
	_split(linked)
	assert f"    .irq_i({{{IRQ}, {DEBUG}}})\n" in _instance_lines(linked)
	nets, ports = _ad_hoc_nets(linked)
	assert (IRQ, 4) in nets and (DEBUG, 4) in nets
	assert ports["cpu"]["irq_i"] == {(7, 4): IRQ, (3, 0): DEBUG}


@pytest.mark.parametrize(
	"cpu, high, low, sources, written",
	[
		(("7", "0"), ("3", "0"), ("7", "4"), ("3", "0"), f"{{{DEBUG}, {IRQ}}}"),
		(("0", "7"), ("0", "3"), ("4", "7"), ("0", "3"), f"{{{IRQ}, {DEBUG}}}"),
		(("0", "7"), ("4", "7"), ("0", "3"), ("0", "3"), f"{{{DEBUG}, {IRQ}}}"),
		(("1", "0"), ("1", "1"), ("0", "0"), None, f"{{{IRQ}, {DEBUG}}}"),
	],
)
def test_parts_follow_the_ports_bit_order(linked, cpu, high, low, sources, written):
	if sources:
		_split(linked, cpu, high, low, sources)
	else:  # one bit each: uart.irq_o and debug.debug_req_o keep no range
		_set_range(linked, "cpu", "irq_i", *cpu)
		_select(_reference(linked, IRQ, "irq_i"), *high)
		_move_debug_to_irq_i(linked)
		_select(_reference(linked, DEBUG, "irq_i"), *low)
	assert f"    .irq_i({written})\n" in _instance_lines(linked)


def test_range_that_covers_the_whole_port_is_the_whole_port(linked):
	_set_range(linked, "cpu", "irq_i", "7", "0")
	_set_range(linked, "uart", "irq_o", "7", "0")
	_select(_reference(linked, IRQ, "irq_i"), "7", "0")
	assert _ad_hoc_nets(linked)[1]["cpu"]["irq_i"] == {None: IRQ}
	assert f"    .irq_i({IRQ}),\n" in _instance_lines(linked)


def test_range_bounds_can_be_expressions(linked):
	_split(linked, high=("3+4", "8/2"))
	assert f"    .irq_i({{{IRQ}, {DEBUG}}})\n" in _instance_lines(linked)


def test_part_on_a_top_port_net_is_the_top_port(linked):
	_set_range(linked, "uart", "tx_o", "1", "0")
	_select(_reference(linked, TX, "tx_o"), "1", "1")
	assert "    .tx_o({uart_tx_o, uart_tx_o_0_0}),\n" in _instance_lines(linked)


# Decision 2: opposite bit orders are refused.

def test_parts_with_opposite_bit_orders_are_refused(linked):
	_set_range(linked, "cpu", "irq_i", "7", "0")
	_set_range(linked, "uart", "irq_o", "0", "3")
	_select(_reference(linked, IRQ, "irq_i"), "7", "4")
	message = "opposite bit orders (uart.irq_o [0:3], cpu.irq_i [7:4])"
	with pytest.raises(ValueError, match=re.escape(message)):
		_ad_hoc_nets(linked)


# Decision 3: which ranges are accepted.

@pytest.mark.parametrize(
	"left, right, message",
	[
		("9", "6", "[9:6], outside the port's bounds [7:0]"),
		("7", "8", "[7:8], outside the port's bounds [7:0]"),
		("4", "7", "[4:7], which runs against the port's [7:0]"),
		("-1", "0", "the left bound of its range, -1, works out to -1, not a whole number of 0"),
		("7", "1.5", "the right bound of its range, 1.5, works out to 1.5, not a whole number"),
		("WIDTH", "4", "the left bound of its range, WIDTH, cannot be worked out"),
	],
)
def test_range_rtlgen_cant_select_is_refused(linked, left, right, message):
	_set_range(linked, "cpu", "irq_i", "7", "0")
	_set_range(linked, "uart", "irq_o", "3", "0")
	_select(_reference(linked, IRQ, "irq_i"), left, right)
	prefix = f"ad hoc connection '{IRQ}' takes part of port 'irq_i' of instance 'cpu'"
	with pytest.raises(ValueError, match="^" + re.escape(prefix) + ".*" + re.escape(message)):
		_ad_hoc_nets(linked)


def test_range_naming_a_parameter_of_the_instance_is_refused(linked):  # it is in the design
	_set_range(linked, "uart", "irq_o", "15", "0")
	_set_range(linked, "cpu", "irq_i", "3", "0")
	_select(_reference(linked, IRQ, "irq_o"), "BAUDRATE/2400-1", "0")  # BAUDRATE is uart's
	with pytest.raises(ValueError, match="BAUDRATE/2400-1, cannot be worked out"):
		_ad_hoc_nets(linked)


def test_single_bit_is_accepted(linked):
	_set_range(linked, "uart", "irq_o", "7", "0")
	_select(_reference(linked, IRQ, "irq_o"), "5", "5")
	assert _ad_hoc_nets(linked)[1]["uart"]["irq_o"] == {(5, 5): IRQ}


@pytest.mark.parametrize(
	"part_select, message",
	[
		(ipxact.PartSelect(indices=[ipxact.Expression(value="0")]), "by indices (partSelect)"),
		(ipxact.PartSelect(), "but its partSelect has no range"),
	],
)
def test_part_select_without_a_range_is_refused(linked, part_select, message):
	_set_range(linked, "cpu", "irq_i", "7", "0")
	_reference(linked, IRQ, "irq_i").source.part_select = part_select
	with pytest.raises(ValueError, match=re.escape(message)):
		_ad_hoc_nets(linked)


def test_part_of_a_port_with_no_range_is_refused(linked):
	_select(_reference(linked, IRQ, "irq_i"), "0", "0")
	with pytest.raises(ValueError, match="the port is one bit with no range to select from"):
		_ad_hoc_nets(linked)


# Decision 4: only connections at the same bits are one net; partial overlaps are refused.

def test_connections_at_the_same_bits_are_one_net(linked):
	_split(linked, low=("7", "4"))
	nets, ports = _ad_hoc_nets(linked)
	assert (IRQ, 4) in nets and DEBUG not in [net for net, width in nets]
	assert ports["cpu"]["irq_i"] == {(7, 4): IRQ}
	assert ports["debug"]["debug_req_o"] == {None: IRQ}


@pytest.mark.parametrize(
	"high, low, message",
	[
		(("7", "4"), ("5", "2"), "([7:4] and [5:2])"),
		(("7", "0"), ("3", "0"), "(the whole port and [3:0])"),
	],
)
def test_connections_at_bits_that_partly_overlap_are_refused(linked, high, low, message):
	_split(linked, high=high, low=low)
	if high == ("7", "0"):
		_set_range(linked, "uart", "irq_o", "7", "0")
	who = f"ad hoc connections '{IRQ}' and '{DEBUG}' reach port 'irq_i' of instance 'cpu'"
	with pytest.raises(ValueError, match=re.escape(f"{who} at bits that partly overlap {message}")):
		_ad_hoc_nets(linked)


# Decision 5: bits that no connection reaches.

def test_input_bits_no_connection_reaches_are_refused(linked):
	_set_range(linked, "cpu", "irq_i", "7", "0")
	_set_range(linked, "uart", "irq_o", "3", "0")
	_select(_reference(linked, IRQ, "irq_i"), "7", "4")
	message = "bits [3:0] of port 'irq_i' of instance 'cpu', an input, are reached by no connection"
	with pytest.raises(ValueError, match=re.escape(message)):
		_instance_lines(linked)


@pytest.mark.parametrize("direction", [ipxact.Direction.OUT, ipxact.Direction.INOUT])
@pytest.mark.parametrize(
	"selected, written, unused",
	[
		(("7", "4"), f"{{{IRQ}, uart_irq_o_3_0}}", [("uart_irq_o_3_0", 4)]),
		(("3", "0"), f"{{uart_irq_o_7_4, {IRQ}}}", [("uart_irq_o_7_4", 4)]),
		(
			("5", "2"), f"{{uart_irq_o_7_6, {IRQ}, uart_irq_o_1_0}}",
			[("uart_irq_o_7_6", 2), ("uart_irq_o_1_0", 2)],
		),
	],
)
def test_output_bits_no_connection_reaches_get_an_unused_wire(
	linked, direction, selected, written, unused
):
	_port(linked, "uart", "irq_o").wire.direction = direction
	_set_range(linked, "uart", "irq_o", "7", "0")
	_set_range(linked, "cpu", "irq_i", "3", "0")
	_select(_reference(linked, IRQ, "irq_o"), *selected)
	connections, wires = _port_connections(linked)
	assert connections["uart"]["irq_o"] == written
	assert wires == unused


def test_unused_wire_that_clashes_with_a_net_is_refused(linked):
	_set_range(linked, "uart", "irq_o", "7", "0")
	_set_range(linked, "cpu", "irq_i", "3", "0")
	_select(_reference(linked, IRQ, "irq_o"), "7", "4")
	linked.ad_hoc_connections["uart_irq_o_3_0"] = linked.ad_hoc_connections.pop(DEBUG)
	next(a for a in linked.design.ad_hoc_connections if a.name == DEBUG).name = "uart_irq_o_3_0"
	message = (
		"the unused wire 'uart_irq_o_3_0' for bits [3:0] of port 'irq_o' of instance 'uart' has "
		"the same name as ad hoc net 'uart_irq_o_3_0'"
	)
	with pytest.raises(ValueError, match=re.escape(message)):
		_instance_lines(linked)


def test_export_declares_the_unused_wire_with_the_nets(library, linked, tmp_path):
	_set_range(linked, "uart", "irq_o", "7", "0")
	_set_range(linked, "cpu", "irq_i", "3", "0")
	_select(_reference(linked, IRQ, "irq_o"), "7", "4")  # on the design's own port reference
	RtlExporter().export(library, tmp_path)
	expected = (
		EXPECTED_SOC_A
		.replace(f"  wire {IRQ};\n", f"  wire [3:0] {IRQ};\n")
		.replace(f"  wire {DEBUG};\n", f"  wire {DEBUG};\n  wire [3:0] uart_irq_o_3_0;\n")
		.replace(f"    .irq_o({IRQ})\n", f"    .irq_o({{{IRQ}, uart_irq_o_3_0}})\n")
	)
	assert (tmp_path / "soc_a.sv").read_text() == expected


# Decision 6: ties on part of a port.

def test_tie_on_part_of_an_input_is_sized_to_the_part(linked):
	_split(linked)
	_tie(linked, DEBUG, "2", "irq_i")
	assert f"    .irq_i({{{IRQ}, 4'h2}})\n" in _instance_lines(linked)


def test_tie_too_big_for_the_part_is_refused(linked):
	_split(linked, low=("2", "0"), high=("7", "3"))
	_set_range(linked, "uart", "irq_o", "4", "0")
	_tie(linked, DEBUG, "4'hF", "irq_i")
	message = "ties bits [2:0] of port 'irq_i' of instance 'cpu' (3 bits) to 4'hF, which works out"
	with pytest.raises(ValueError, match=re.escape(message)):
		_instance_lines(linked)


def test_open_tie_on_part_of_an_input_gets_an_unused_wire(linked):
	_split(linked)
	_tie(linked, DEBUG, "open", "irq_i")
	connections, wires = _port_connections(linked)
	assert connections["cpu"]["irq_i"] == f"{{{IRQ}, cpu_irq_i_3_0}}"
	assert wires == [("cpu_irq_i_3_0", 4)]


def test_default_tie_on_part_of_a_port_is_refused(linked):
	_split(linked)
	_tie(linked, DEBUG, "default", "irq_i")
	with pytest.raises(ValueError, match="the default value of part of a port is not supported"):
		_instance_lines(linked)


def test_tie_on_part_of_an_output_is_refused(linked):
	_set_range(linked, "uart", "irq_o", "3", "0")
	_select(_reference(linked, IRQ, "irq_o"), "3", "2")
	_tie(linked, IRQ, "0", "irq_o")
	message = "ties bits [3:2] of port 'irq_o' of instance 'uart', an output, to a value"
	with pytest.raises(ValueError, match=re.escape(message)):
		_instance_lines(linked)


def test_tie_and_net_at_the_same_bits_are_refused(linked):  # step 7c decision 6, by bits
	_split(linked, low=("7", "4"))
	_tie(linked, DEBUG, "0", "irq_i")
	message = (
		f"bits [7:4] of port 'irq_i' of instance 'cpu' are tied by ad hoc connection '{DEBUG}' "
		f"and are also in ad hoc connection '{IRQ}'"
	)
	with pytest.raises(ValueError, match=re.escape(message)):
		_instance_lines(linked)
