"""Step 7c: ad hoc connections with a tiedValue. Each case ties one of the linked example's ad
hoc connections, keeping only the port references it names."""
import dataclasses
import re

import ipxact
import pytest

from conftest import EXPECTED_SOC_A
from rtlgen import RtlExporter, _ad_hoc_nets, _assign_lines, _instance_lines

IRQ = "uart_irq_o_to_cpu_irq_i"
DEBUG = "debug_debug_req_o_to_cpu_debug_req_i"
RX = "uart_rx_i_to_uart_rx_i"
TX = "uart_tx_o_to_uart_tx_o"


def _port(linked, instance, port_name):
	"""A port of an instance's component."""
	return next(p for p in linked.instances[instance].component.model.ports if p.name == port_name)


def _set_range(linked, instance, port_name, left, right):
	"""Give a port of an instance's component the range [left:right]."""
	_port(linked, instance, port_name).wire.vectors = [
		ipxact.Vector(left=ipxact.Expression(value=left), right=ipxact.Expression(value=right))
	]


def _tie(linked, connection, value, *keep):
	"""Tie an ad hoc connection to value, keeping only the instance ports named in keep, and its
	top port when 'top' is in keep."""
	next(a for a in linked.design.ad_hoc_connections if a.name == connection).tied_value = (
		ipxact.Expression(value=value)
	)
	references = linked.ad_hoc_connections[connection]
	references[:] = [r for r in references if r.port.name in keep]
	if "top" not in keep:
		linked.ad_hoc_external_ports[connection] = []


def _reference(linked, connection, instance, port_name):
	"""A reference to a port of an instance, made from the first reference of a connection."""
	return dataclasses.replace(
		linked.ad_hoc_connections[connection][0],
		instance=linked.instances[instance],
		port=_port(linked, instance, port_name),
	)


# Decisions 1 and 2: a tie is the constant in the port's connection, sized to the port.

@pytest.mark.parametrize(
	"bounds, value, written",
	[
		(None, "0", "1'b0"),
		(None, "1'b1", "1'b1"),
		(("15", "0"), "255", "16'hff"),
		(("15", "0"), "16'hFF", "16'hff"),
		(("0", "7"), "8'b1010_0101", "8'ha5"),
		(("7", "0"), "2+3", "8'h5"),
		(("3", "0"), "4'hF", "4'hf"),
		(("3", "0"), "0", "4'h0"),
	],
)
def test_tie_is_written_sized_in_the_port_connection(linked, bounds, value, written):
	if bounds:
		_set_range(linked, "cpu", "irq_i", *bounds)
	_tie(linked, IRQ, value, "irq_i")
	assert f"    .irq_i({written}),\n" in _instance_lines(linked)


def test_tied_connection_makes_no_net(linked):
	_tie(linked, IRQ, "0", "irq_i")
	nets, ports = _ad_hoc_nets(linked)
	assert IRQ not in [net for net, width in nets]
	assert "irq_i" not in ports["cpu"]


def test_tie_takes_the_width_from_the_instance_parameters(linked):
	_set_range(linked, "uart", "rx_i", "BAUDRATE/1200-1", "0")  # BAUDRATE is 9600: 8 bits
	_tie(linked, RX, "200", "rx_i")
	assert "    .rx_i(8'hc8),\n" in _instance_lines(linked)


def test_tie_on_several_ports_is_sized_for_each(linked):
	_set_range(linked, "uart", "rx_i", "3", "0")
	_tie(linked, IRQ, "1", "irq_i")
	linked.ad_hoc_connections[IRQ].append(_reference(linked, IRQ, "uart", "rx_i"))
	linked.ad_hoc_connections[RX] = []  # uart.rx_i is now tied instead
	lines = _instance_lines(linked)
	assert "    .irq_i(1'b1),\n" in lines
	assert "    .rx_i(4'h1),\n" in lines


def test_port_listed_twice_in_a_tie_is_written_once(linked):
	_tie(linked, IRQ, "1", "irq_i")
	linked.ad_hoc_connections[IRQ].append(linked.ad_hoc_connections[IRQ][0])
	assert _instance_lines(linked).count(".irq_i(1'b1)") == 1


# Decision 3: a value ties an instance input or drives a top output; on any other port it is
# refused.

def test_tie_on_a_top_output_is_an_assign(linked):
	_tie(linked, TX, "1", "top")
	assert _assign_lines(linked) == "  assign uart_tx_o = 1'b1;\n\n"
	assert "    .tx_o(),\n" in _instance_lines(linked)  # uart.tx_o is now open (step 7a)


def test_export_writes_the_assign_after_the_wires(library, tmp_path):
	design = next(library.targets(ipxact.Design))
	connection = next(a for a in design.ad_hoc_connections if a.name == TX)
	connection.tied_value = ipxact.Expression(value="1")
	connection.internal_port_references = []
	RtlExporter().export(library, tmp_path)
	expected = EXPECTED_SOC_A.replace(
		"  cpu cpu (\n", "  assign uart_tx_o = 1'b1;\n\n  cpu cpu (\n"
	).replace("    .tx_o(uart_tx_o),\n", "    .tx_o(),\n")
	assert (tmp_path / "soc_a.sv").read_text() == expected


@pytest.mark.parametrize(
	"direction, kind", [(ipxact.Direction.OUT, "an output"), (ipxact.Direction.INOUT, "an inout")]
)
def test_tie_on_an_instance_output_or_inout_is_refused(linked, direction, kind):
	_port(linked, "cpu", "irq_i").wire.direction = direction
	_tie(linked, IRQ, "0", "irq_i")
	message = f"ad hoc connection '{IRQ}' ties port 'irq_i' of instance 'cpu', {kind}, to a value"
	with pytest.raises(ValueError, match=re.escape(message)):
		_instance_lines(linked)


def test_tie_on_a_top_input_is_refused(linked):
	_tie(linked, RX, "0", "top")
	with pytest.raises(ValueError, match="ties top port 'uart_rx_i', an input, to a value"):
		_instance_lines(linked)


def test_tie_on_a_top_inout_is_refused(linked):
	linked.ad_hoc_external_ports[TX][0].port.wire.direction = ipxact.Direction.INOUT
	_tie(linked, TX, "0", "top")
	with pytest.raises(ValueError, match="ties top port 'uart_tx_o', an inout, to a value"):
		_instance_lines(linked)


# Decision 4: 'open' leaves every port it names open, inputs and outputs, instance and top
# ports.

@pytest.mark.parametrize("value", ["open", " open "])
def test_open_tie_leaves_instance_ports_open(linked, value):
	_tie(linked, IRQ, value, "irq_o", "irq_i")
	lines = _instance_lines(linked)
	assert "    .irq_o()\n" in lines
	assert "    .irq_i(),\n" in lines


def test_open_tie_on_a_top_output_leaves_it_undriven(linked):
	_tie(linked, TX, "open", "tx_o", "top")
	_ad_hoc_nets(linked)  # not refused as a top output that nothing drives
	assert _assign_lines(linked) == ""
	assert "    .tx_o(),\n" in _instance_lines(linked)


def test_open_tie_on_a_top_input_leaves_it_unused(linked):
	_tie(linked, RX, "open", "rx_i", "top")
	assert "    .rx_i(),\n" in _instance_lines(linked)
	assert _assign_lines(linked) == ""


# Decision 5: 'default' ties a port to its own default value.

def _give_default(linked, instance, port_name, *values):
	_port(linked, instance, port_name).wire.drivers = [
		ipxact.Driver(default_value=ipxact.Expression(value=value)) for value in values
	]


def test_default_tie_writes_the_ports_default_value(linked):
	_give_default(linked, "cpu", "irq_i", "1")
	_tie(linked, IRQ, "default", "irq_i")
	assert "    .irq_i(1'b1),\n" in _instance_lines(linked)


def test_default_value_takes_the_instance_parameters(linked):
	_set_range(linked, "uart", "rx_i", "7", "0")
	_give_default(linked, "uart", "rx_i", "BAUDRATE/1200")  # BAUDRATE is 9600
	_tie(linked, RX, "default", "rx_i")
	assert "    .rx_i(8'h8),\n" in _instance_lines(linked)


def test_default_tie_on_a_port_with_no_default_is_refused(linked):
	_tie(linked, IRQ, "default", "irq_i")
	with pytest.raises(ValueError, match=re.escape("but the port has none (SCR 6.25)")):
		_instance_lines(linked)


def test_default_tie_on_a_top_output_is_refused(linked):
	_tie(linked, TX, "default", "top")
	with pytest.raises(ValueError, match=re.escape("an output has no default value (SCR 6.23)")):
		_instance_lines(linked)


@pytest.mark.parametrize(
	"change, message",
	[
		(lambda d: d.append(d[0]), "the port has 2 drivers"),
		(
			lambda d: d.__setitem__(0, ipxact.Driver(
				clock_driver=ipxact.ClockDriver(*(ipxact.Expression(value="1") for _ in range(4)))
			)),
			"its driver is a clockDriver or singleShotDriver",
		),
		(
			lambda d: setattr(d[0], "range", ipxact.Range(
				left=ipxact.Expression(value="0"), right=ipxact.Expression(value="0")
			)),
			"only for part of the port (range)",
		),
		(lambda d: d[0].view_refs.append(ipxact.TextValue(value="rtl")), "for some views (viewRef)"),
	],
)
def test_default_tie_on_a_driver_rtlgen_cant_write_is_refused(linked, change, message):
	_give_default(linked, "cpu", "irq_i", "1")
	change(_port(linked, "cpu", "irq_i").wire.drivers)
	_tie(linked, IRQ, "default", "irq_i")
	with pytest.raises(ValueError, match=re.escape(message)):
		_instance_lines(linked)


def test_default_value_too_big_for_the_port_is_refused(linked):  # decision 7
	_give_default(linked, "cpu", "irq_i", "4'hF")
	_tie(linked, IRQ, "default", "irq_i")
	message = "(1 bit) to its default value 4'hF, which works out to 15: too big for the port"
	with pytest.raises(ValueError, match=re.escape(message)):
		_instance_lines(linked)


# Decision 6: a tied port can't be in another connection.

def test_tied_port_in_another_ad_hoc_connection_is_refused(linked):
	_tie(linked, IRQ, "0", "irq_i")
	linked.ad_hoc_connections[DEBUG].append(linked.ad_hoc_connections[IRQ][0])
	message = (
		f"port 'irq_i' of instance 'cpu' is tied by ad hoc connection '{IRQ}' and is also in "
		f"ad hoc connection '{DEBUG}'"
	)
	with pytest.raises(ValueError, match=re.escape(message)):
		_instance_lines(linked)


def test_port_in_two_tied_connections_is_refused(linked):
	_tie(linked, IRQ, "0", "irq_i")
	_tie(linked, DEBUG, "0", "debug_req_i")
	linked.ad_hoc_connections[DEBUG].append(linked.ad_hoc_connections[IRQ][0])
	with pytest.raises(ValueError, match=f"is tied by ad hoc connection '{IRQ}' and is also in"):
		_instance_lines(linked)


def test_tied_top_output_that_an_instance_drives_is_refused(linked):
	linked.design.ad_hoc_connections.append(
		ipxact.AdHocConnection(name="tie_tx", tied_value=ipxact.Expression(value="1"))
	)
	linked.ad_hoc_external_ports["tie_tx"] = list(linked.ad_hoc_external_ports[TX])
	message = (
		f"top port 'uart_tx_o' is tied by ad hoc connection 'tie_tx' and is also in ad hoc "
		f"connection '{TX}'"
	)
	with pytest.raises(ValueError, match=re.escape(message)):
		_instance_lines(linked)


def test_tied_port_on_a_bus_net_is_refused(linked):
	_tie(linked, IRQ, "0")
	linked.ad_hoc_connections[IRQ].append(_reference(linked, DEBUG, "uart", "psel_i"))
	message = (
		"port 'psel_i' of instance 'uart' is on bus net 'bus_to_uart_PSEL' of interconnection "
		f"'bus_to_uart' and is tied by ad hoc connection '{IRQ}'"
	)
	with pytest.raises(ValueError, match=re.escape(message)):
		_instance_lines(linked)


# Decision 7: the value must be a whole number from 0 to 2^W - 1.

@pytest.mark.parametrize(
	"bounds, value, message",
	[
		(None, "2", "(1 bit) to 2, which works out to 2: too big for the port"),
		(("3", "0"), "16'hFFFF", "(4 bits) to 16'hFFFF, which works out to 65535: too big"),
		(None, "-1", "which works out to -1: a tie value can't be negative"),
		(("7", "0"), "8'sd255", "which works out to -1: a tie value can't be negative"),
		(None, "1.5", "which works out to 1.5: a tie value is a whole number"),
		(None, "2.0", "which works out to 2.0: a tie value is a whole number"),
		(None, "'1", "to '1: fill literals ('0, '1, 'x, 'z) are not supported"),
		(("3", "0"), "'0", "to '0: fill literals"),
		(("3", "0"), "4'bx01z", "to 4'bx01z, which cannot be worked out"),
		(None, '"open"', 'to "open", which cannot be worked out'),
		(None, "Open", "to Open, which cannot be worked out"),
		(None, "WIDTH", "to WIDTH, which cannot be worked out"),
	],
)
def test_value_that_is_not_an_unsigned_bit_vector_of_the_port_is_refused(
	linked, bounds, value, message
):
	if bounds:
		_set_range(linked, "cpu", "irq_i", *bounds)
	_tie(linked, IRQ, value, "irq_i")
	prefix = f"ad hoc connection '{IRQ}' ties port 'irq_i' of instance 'cpu' "
	with pytest.raises(ValueError, match="^" + re.escape(prefix) + ".*" + re.escape(message)):
		_instance_lines(linked)


def test_value_naming_a_parameter_of_the_instance_is_refused(linked):  # it is in the design
	_set_range(linked, "uart", "rx_i", "15", "0")
	_tie(linked, RX, "BAUDRATE", "rx_i")
	with pytest.raises(ValueError, match="to BAUDRATE, which cannot be worked out"):
		_instance_lines(linked)
