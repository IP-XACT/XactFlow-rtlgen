import dataclasses

import ipxact
import pytest

from rtlgen import RtlExporter, _ad_hoc_groups, _ad_hoc_nets, _instance_lines


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


def _reference(linked, connection, port_name):
	"""The reference to a port in an ad hoc connection."""
	return next(r for r in linked.ad_hoc_connections[connection] if r.port.name == port_name)


def test_ports_in_component_order(linked):
	linked.ad_hoc_connections = dict(reversed(list(linked.ad_hoc_connections.items())))
	lines = _instance_lines(linked)
	assert lines.index(".irq_i(") < lines.index(".debug_req_i(")


def test_connection_to_a_top_port_is_written_to_the_port(linked):
	nets, ports = _ad_hoc_nets(linked)
	assert ports["cpu"]["clk_i"] == "clk_i"
	assert "clk_i" not in [net for net, width in nets]


@pytest.mark.parametrize(
	"uart, cpu",
	[(("7", "0"), ("7", "0")), (("15", "8"), ("7", "0")), (("BAUDRATE/1200-1", "0"), ("7", "0"))],
)
def test_net_takes_the_ports_width(linked, uart, cpu):
	_set_range(linked, "uart", "irq_o", *uart)
	_set_range(linked, "cpu", "irq_i", *cpu)
	nets, _ = _ad_hoc_nets(linked)
	assert ("uart_irq_o_to_cpu_irq_i", 8) in nets


@pytest.mark.parametrize(
	"cpu, message", [(("3", "0"), "different widths"), (("0", "7"), "opposite bit orders")]
)
def test_ports_that_do_not_match_are_refused(linked, cpu, message):
	_set_range(linked, "uart", "irq_o", "7", "0")
	_set_range(linked, "cpu", "irq_i", *cpu)
	with pytest.raises(ValueError, match=message):
		_ad_hoc_nets(linked)


def test_wide_net_is_declared_with_its_range(library, linked, tmp_path):
	_set_range(linked, "uart", "irq_o", "7", "0")
	_set_range(linked, "cpu", "irq_i", "7", "0")
	RtlExporter().export(library, tmp_path)
	assert "  wire [7:0] uart_irq_o_to_cpu_irq_i;\n" in (tmp_path / "soc_a.sv").read_text()


@pytest.mark.parametrize("direction", [ipxact.Direction.OUT, ipxact.Direction.INOUT])
def test_several_drivers_and_inouts_are_accepted(linked, direction):
	_port(linked, "cpu", "irq_i").wire.direction = direction
	nets, _ = _ad_hoc_nets(linked)
	assert ("uart_irq_o_to_cpu_irq_i", 1) in nets


def test_phantom_port_is_refused(linked):
	_port(linked, "cpu", "irq_i").wire.direction = ipxact.Direction.PHANTOM
	with pytest.raises(ValueError, match="phantom"):
		_ad_hoc_nets(linked)


def test_connections_sharing_a_port_are_one_net(linked):
	linked.ad_hoc_connections[DEBUG].append(_reference(linked, IRQ, "irq_i"))
	nets, ports = _ad_hoc_nets(linked)
	assert nets == [(IRQ, 1)]
	assert ports["cpu"]["irq_i"] == IRQ
	assert ports["cpu"]["debug_req_i"] == IRQ
	assert ports["debug"]["debug_req_o"] == IRQ


def test_a_later_connection_joins_two_nets(linked):
	linked.design.ad_hoc_connections.append(ipxact.AdHocConnection(name="bridge"))
	linked.ad_hoc_connections["bridge"] = [
		_reference(linked, IRQ, "irq_o"), _reference(linked, DEBUG, "debug_req_o")
	]
	assert _ad_hoc_nets(linked)[0] == [(IRQ, 1)]


def test_port_twice_in_one_connection_is_written_once(linked):
	linked.ad_hoc_connections[IRQ].append(_reference(linked, IRQ, "irq_i"))
	assert _instance_lines(linked).count(".irq_i(") == 1


def test_net_sharing_a_port_with_a_top_port_connection_joins_its_net(linked):
	_port(linked, "uart", "irq_o").wire.direction = ipxact.Direction.IN
	linked.ad_hoc_connections[IRQ].append(_reference(linked, "clk_i_to_cpu_clk_i", "clk_i"))
	nets, ports = _ad_hoc_nets(linked)
	assert ports["uart"]["irq_o"] == "clk_i"
	assert ports["cpu"]["irq_i"] == "clk_i"
	assert IRQ not in [net for net, width in nets]


def test_connections_to_one_top_port_are_one_net(linked):
	clk = [
		"clk_i_to_cpu_clk_i", "clk_i_to_bus_clk_i", "clk_i_to_uart_clk_i",
		"clk_i_to_gpio_clk_i", "clk_i_to_debug_clk_i",
	]
	assert clk in _ad_hoc_groups(linked)


def test_net_reaching_two_top_ports_is_refused(linked):
	external = linked.ad_hoc_external_ports
	external["clk_i_to_cpu_clk_i"].append(external["rst_ni_to_cpu_rst_ni"][0])
	with pytest.raises(ValueError, match="joins top ports 'clk_i', 'rst_ni'"):
		_ad_hoc_nets(linked)


def test_non_wire_port_is_refused(linked):
	_port(linked, "cpu", "irq_i").wire = None
	with pytest.raises(ValueError, match="not a wire port"):
		_ad_hoc_nets(linked)


def test_port_array_is_refused(linked):
	_port(linked, "cpu", "irq_i").arrays = [
		ipxact.ArrayBound(left=ipxact.Expression(value="3"), right=ipxact.Expression(value="0"))
	]
	with pytest.raises(ValueError, match="an array"):
		_ad_hoc_nets(linked)


def test_part_select_is_refused(linked):
	_reference(linked, IRQ, "irq_i").source.part_select = ipxact.PartSelect()
	with pytest.raises(ValueError, match="partSelect"):
		_ad_hoc_nets(linked)


def test_sub_port_reference_is_refused(linked):
	_reference(linked, IRQ, "irq_i").source.sub_port_refs = [ipxact.SubPortReference(sub_port_ref="x")]
	with pytest.raises(ValueError, match="subPortReference"):
		_ad_hoc_nets(linked)


def test_tied_value_is_refused(linked):
	connection = next(a for a in linked.design.ad_hoc_connections if a.name == IRQ)
	connection.tied_value = ipxact.Expression(value="0")
	with pytest.raises(ValueError, match="tiedValue"):
		_ad_hoc_nets(linked)


def _rename(linked, old, new):
	"""Rename an ad hoc connection, in the linked design and in the design as written."""
	linked.ad_hoc_connections[new] = linked.ad_hoc_connections.pop(old)
	next(a for a in linked.design.ad_hoc_connections if a.name == old).name = new


def test_connection_name_that_is_not_an_identifier_is_refused(linked):
	_rename(linked, IRQ, "irq-net")
	with pytest.raises(ValueError, match="ad hoc connection name 'irq-net'"):
		_ad_hoc_nets(linked)


def test_net_named_like_an_instance_is_refused(linked):
	_rename(linked, IRQ, "uart")
	with pytest.raises(ValueError, match="same name as an instance"):
		_ad_hoc_nets(linked)


def test_net_named_like_a_top_port_is_refused(linked):
	_rename(linked, IRQ, "uart_tx_o")
	with pytest.raises(ValueError, match="same name as a top port"):
		_ad_hoc_nets(linked)


def test_net_named_like_a_phantom_top_port_is_accepted(linked):
	linked.component.model.ports.append(
		ipxact.Port(name="spare", wire=ipxact.WirePort(direction=ipxact.Direction.PHANTOM))
	)
	_rename(linked, IRQ, "spare")
	assert ("spare", 1) in _ad_hoc_nets(linked)[0]


def test_port_name_that_is_not_an_identifier_is_refused(linked):
	_port(linked, "cpu", "irq_i").name = "irq-i"
	with pytest.raises(ValueError, match="port name 'irq-i'"):
		_ad_hoc_nets(linked)


def test_two_connections_with_one_name_are_refused(linked):
	linked.design.ad_hoc_connections.append(ipxact.AdHocConnection(name=IRQ))
	with pytest.raises(ValueError, match="two ad hoc connections named"):
		_ad_hoc_nets(linked)


def test_merged_net_names_all_its_connections(linked):
	linked.ad_hoc_connections[DEBUG].append(_reference(linked, IRQ, "irq_i"))
	_set_range(linked, "uart", "irq_o", "7", "0")
	with pytest.raises(ValueError, match=f"^ad hoc connections '{IRQ}', '{DEBUG}' "):
		_ad_hoc_nets(linked)


RX = "uart_rx_i_to_uart_rx_i"
TX = "uart_tx_o_to_uart_tx_o"


def test_instance_output_on_a_top_input_is_refused(linked):  # decision 8
	_port(linked, "uart", "rx_i").wire.direction = ipxact.Direction.OUT
	with pytest.raises(ValueError, match="drives top input 'uart_rx_i' from instance output.* uart.rx_i"):
		_ad_hoc_nets(linked)


def test_top_output_with_no_driver_is_refused(linked):  # decision 8
	_port(linked, "uart", "tx_o").wire.direction = ipxact.Direction.IN
	with pytest.raises(ValueError, match="top output 'uart_tx_o', but no output or inout drives it"):
		_ad_hoc_nets(linked)


@pytest.mark.parametrize("instance, port_name", [("uart", "rx_i"), ("uart", "tx_o")])
def test_inout_on_a_top_port_is_accepted(linked, instance, port_name):  # decision 8
	_port(linked, instance, port_name).wire.direction = ipxact.Direction.INOUT
	_ad_hoc_nets(linked)


def test_top_output_driven_through_another_connection_is_accepted(linked):  # merge on top ports
	linked.design.ad_hoc_connections.append(ipxact.AdHocConnection(name="tx_tap"))
	linked.ad_hoc_connections["tx_tap"] = [
		dataclasses.replace(_reference(linked, IRQ, "irq_i"), port=_port(linked, "cpu", "pready_i"))
	]
	linked.ad_hoc_external_ports["tx_tap"] = list(linked.ad_hoc_external_ports[TX])
	assert _ad_hoc_nets(linked)[1]["cpu"]["pready_i"] == "uart_tx_o"


def _add_top_port(linked, name, direction):
	"""Add a one-bit wire port to the containing component."""
	linked.component.model.ports.append(ipxact.Port(name=name, wire=ipxact.WirePort(direction=direction)))


def test_top_output_no_connection_reaches_is_refused(linked):  # decision 8
	_add_top_port(linked, "spare_o", ipxact.Direction.OUT)
	with pytest.raises(ValueError, match="top output 'spare_o' .* is not reached by any connection"):
		_ad_hoc_nets(linked)


def test_top_input_no_connection_reaches_is_accepted(linked):  # decision 9
	_add_top_port(linked, "spare_i", ipxact.Direction.IN)
	_ad_hoc_nets(linked)


def _external(linked, connection):
	"""The first top-port reference of an ad hoc connection."""
	return linked.ad_hoc_external_ports[connection][0]


def test_non_wire_top_port_reference_is_refused(linked):  # decision 11
	_external(linked, TX).port.wire = None
	with pytest.raises(ValueError, match="top port 'uart_tx_o', which is not a wire port"):
		_ad_hoc_nets(linked)


def test_phantom_top_port_reference_is_refused(linked):  # decision 10
	_external(linked, TX).port.wire.direction = ipxact.Direction.PHANTOM
	with pytest.raises(ValueError, match="top port 'uart_tx_o', which is phantom"):
		_ad_hoc_nets(linked)


def test_part_select_on_a_top_port_is_refused(linked):  # decision 11
	_external(linked, TX).source.part_select = ipxact.PartSelect()
	with pytest.raises(ValueError, match="top port 'uart_tx_o' through a partSelect"):
		_ad_hoc_nets(linked)


def test_sub_port_reference_on_a_top_port_is_refused(linked):  # decision 11
	_external(linked, TX).source.sub_port_refs = [ipxact.SubPortReference(sub_port_ref="x")]
	with pytest.raises(ValueError, match="top port 'uart_tx_o' through a subPortReference"):
		_ad_hoc_nets(linked)


def test_tied_value_on_a_top_port_connection_is_refused(linked):  # decision 11
	connection = next(a for a in linked.design.ad_hoc_connections if a.name == TX)
	connection.tied_value = ipxact.Expression(value="0")
	with pytest.raises(ValueError, match=f"ad hoc connection '{TX}' has a tiedValue"):
		_ad_hoc_nets(linked)
