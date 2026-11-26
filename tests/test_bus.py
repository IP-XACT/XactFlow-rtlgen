import dataclasses

import ipxact
import pytest
from xactflow.link.model import LinkedMonitorInterconnection, ResolvedHierInterface

from rtlgen import RtlExporter, _bus_nets

INTERCONNECTIONS = ["cpu_to_bus", "debug_to_bus", "bus_to_uart", "bus_to_gpio", "bus_to_debug"]


def _port_maps(linked, name, end):
	"""The port maps of one end (0 or 1) of an interconnection."""
	interconnection = next(i for i in linked.interconnections if i.name == name)
	return interconnection.endpoints[end].bus_interface.abstraction_types[0].port_maps


def _net_names(linked, index):
	"""The net names of the index-th interconnection, in order."""
	groups, _ = _bus_nets(linked)
	return [net for net, width in groups[index][1]]


def test_one_group_per_interconnection_in_design_order(linked):
	groups, _ = _bus_nets(linked)
	assert [name for name, nets in groups] == INTERCONNECTIONS
	assert all(len(nets) == 10 for name, nets in groups)


def test_net_names_and_widths(linked):  # decisions 2 and 4
	groups, _ = _bus_nets(linked)
	nets = dict(groups[0][1])
	assert nets["cpu_to_bus_PADDR"] == 32
	assert nets["cpu_to_bus_PPROT"] == 3
	assert nets["cpu_to_bus_PSTRB"] == 4
	assert nets["cpu_to_bus_PSEL"] == 1


def test_both_ends_are_on_one_net(linked):  # decision 1
	_, ports = _bus_nets(linked)
	assert ports["cpu"]["paddr_o"] == "cpu_to_bus_PADDR"
	assert ports["bus"]["s0_paddr_i"] == "cpu_to_bus_PADDR"


def test_nets_follow_the_first_ends_port_maps(linked):  # decision 10
	before = _net_names(linked, 0)
	_port_maps(linked, "cpu_to_bus", 1).reverse()
	assert _net_names(linked, 0) == before
	_port_maps(linked, "cpu_to_bus", 0).reverse()
	assert _net_names(linked, 0) == before[::-1]


def test_design_without_interconnections_has_no_bus_wires(library, linked, tmp_path):
	linked.design.interconnections = []
	RtlExporter().export(library, tmp_path)
	text = (tmp_path / "soc_a.sv").read_text()
	assert "//" not in text.split("\n", 1)[1]  # line 1 is rtlgen's own comment
	assert "_PADDR" not in text


def _interconnection(linked, name):
	return next(i for i in linked.interconnections if i.name == name)


def test_monitor_interconnection_is_refused(linked):  # decision 9
	linked.monitor_interconnections.append(
		LinkedMonitorInterconnection(name="watch", monitored_active_interface=None)
	)
	with pytest.raises(ValueError, match="monitor interconnection 'watch'"):
		_bus_nets(linked)


def test_hier_interface_is_refused(linked):  # decision 8
	interconnection = _interconnection(linked, "cpu_to_bus")
	end = interconnection.endpoints.pop()
	hier = ipxact.HierInterface(bus_ref="s0")
	interconnection.hier_interfaces.append(ResolvedHierInterface(end.bus_interface, hier))
	with pytest.raises(ValueError, match="'cpu_to_bus' reaches bus interface 's0' of the top"):
		_bus_nets(linked)


def test_three_active_interfaces_are_refused(linked):  # decision 7
	interconnection = _interconnection(linked, "bus_to_uart")
	interconnection.endpoints.append(_interconnection(linked, "bus_to_gpio").endpoints[1])
	with pytest.raises(ValueError, match="'bus_to_uart' has 3 active interfaces"):
		_bus_nets(linked)


@pytest.mark.parametrize("mode", ["MIRRORED_INITIATOR", "INITIATOR", "SYSTEM"])
def test_pair_other_than_initiator_and_target_is_refused(linked, mode):  # decision 5
	end = _interconnection(linked, "cpu_to_bus").endpoints[1]
	end.bus_interface.mode = ipxact.InterfaceMode[mode]
	value = ipxact.InterfaceMode[mode].value
	message = f"'cpu_to_bus' joins cpu.apb \\(initiator\\) and bus.s0 \\({value}\\)"
	with pytest.raises(ValueError, match=message):
		_bus_nets(linked)


@pytest.mark.parametrize("count", [0, 2])
def test_other_than_one_abstraction_type_is_refused(linked, count):  # decision 9
	bus_interface = _interconnection(linked, "bus_to_uart").endpoints[1].bus_interface
	bus_interface.abstraction_types = bus_interface.abstraction_types[:1] * count
	message = f"interface 'apb' of instance 'uart' .* has {count} abstractionTypes"
	with pytest.raises(ValueError, match=message):
		_bus_nets(linked)


def test_exclude_ports_is_refused(linked):  # decision 9
	end = _interconnection(linked, "bus_to_uart").endpoints[0]
	end.source.exclude_ports = [ipxact.TextValue(value="PSLVERR")]
	message = "interface 'm0' of instance 'bus' .* excludes logical ports PSLVERR"
	with pytest.raises(ValueError, match=message):
		_bus_nets(linked)


def _uart_port_maps(linked):
	"""The port maps of uart's end of bus_to_uart: the second end, so both ends are checked."""
	return _port_maps(linked, "bus_to_uart", 1)


def _uart_port(linked, name):
	"""A port of uart's component."""
	ports = _interconnection(linked, "bus_to_uart").endpoints[1].instance.component.model.ports
	return next(p for p in ports if p.name == name)


_RANGE = ipxact.Range(left=ipxact.Expression(value="7"), right=ipxact.Expression(value="0"))


@pytest.mark.parametrize(
	"field, value, message",
	[
		("is_informative", True, "for information only \\(isInformative\\)"),
		("logical_tie_off", ipxact.Expression(value="0"), "to a constant \\(logicalTieOff\\)"),
		("invert", True, "inverted \\(invert\\)"),
		("logical_range", _RANGE, "in part \\(logicalRange\\)"),
		("part_select", ipxact.PartSelect(), "to part of port 'paddr_i' \\(partSelect\\)"),
		(
			"sub_port_refs",
			[ipxact.SubPortReference(sub_port_ref="x")],
			"to a sub-port of port 'paddr_i' \\(subPortReference\\)",
		),
	],
)
def test_port_map_rtlgen_cannot_wire_is_refused(linked, field, value, message):  # decisions 4, 9
	setattr(_uart_port_maps(linked)[0], field, value)
	with pytest.raises(ValueError, match=f"instance 'uart' .* logical port 'PADDR' {message}"):
		_bus_nets(linked)


def test_logical_port_mapped_twice_is_refused(linked):
	port_maps = _uart_port_maps(linked)
	port_maps.append(dataclasses.replace(port_maps[0], physical_port="pprot_i"))
	with pytest.raises(ValueError, match="instance 'uart' .* logical port 'PADDR' twice"):
		_bus_nets(linked)


def test_port_mapped_twice_is_refused(linked):
	_uart_port_maps(linked)[1].physical_port = "paddr_i"
	message = "maps port 'paddr_i' twice \\(logical ports 'PADDR' and 'PPROT'\\)"
	with pytest.raises(ValueError, match=message):
		_bus_nets(linked)


def test_missing_physical_port_is_refused(linked):  # SCR 2.19, which xactflow does not check
	_uart_port_maps(linked)[0].physical_port = "nope"
	with pytest.raises(ValueError, match="to port 'nope', which the component does not have"):
		_bus_nets(linked)


def test_physical_port_with_a_bad_name_is_refused(linked):
	_uart_port(linked, "paddr_i").name = "9paddr_i"
	_uart_port_maps(linked)[0].physical_port = "9paddr_i"
	with pytest.raises(ValueError, match="port name '9paddr_i' of instance 'uart' is not a legal"):
		_bus_nets(linked)


def test_non_wire_physical_port_is_refused(linked):
	_uart_port(linked, "paddr_i").wire = None
	with pytest.raises(ValueError, match="port 'paddr_i', which is not a wire port"):
		_bus_nets(linked)


def test_phantom_physical_port_is_refused(linked):
	_uart_port(linked, "paddr_i").wire.direction = ipxact.Direction.PHANTOM
	with pytest.raises(ValueError, match="port 'paddr_i', which is phantom"):
		_bus_nets(linked)


def test_array_physical_port_is_refused(linked):
	_uart_port(linked, "paddr_i").arrays = [
		ipxact.ArrayBound(left=ipxact.Expression(value="3"), right=ipxact.Expression(value="0"))
	]
	with pytest.raises(ValueError, match="port 'paddr_i', which is an array"):
		_bus_nets(linked)


@pytest.mark.parametrize("end, instance", [(0, "bus"), (1, "uart")])
def test_logical_port_mapped_by_one_end_only_is_refused(linked, end, instance):  # decision 3
	port_maps = _port_maps(linked, "bus_to_uart", end)
	port_maps[:] = [m for m in port_maps if m.logical_port != "PSLVERR"]
	message = f"of instance '{instance}' does not map logical port\\(s\\) PSLVERR, which the other"
	with pytest.raises(ValueError, match=message):
		_bus_nets(linked)


def _vector(left, right):
	return ipxact.Vector(left=ipxact.Expression(value=left), right=ipxact.Expression(value=right))


@pytest.mark.parametrize(
	"left, right, message",
	[("15", "0", "of different widths"), ("0", "31", "with opposite bit orders")],
)
def test_bus_net_whose_ports_do_not_match_is_refused(linked, left, right, message):  # decision 4
	_uart_port(linked, "paddr_i").wire.vectors = [_vector(left, right)]
	listed = f"bus.m0_paddr_o \\[31:0\\], uart.paddr_i \\[{left}:{right}\\]"
	with pytest.raises(ValueError, match=f"'bus_to_uart_PADDR' joins ports {message} \\({listed}"):
		_bus_nets(linked)


def test_bus_net_with_shifted_bounds_is_accepted(linked):  # D12 item 2
	_uart_port(linked, "paddr_i").wire.vectors = [_vector("32", "1")]
	groups, _ = _bus_nets(linked)
	assert dict(groups[2][1])["bus_to_uart_PADDR"] == 32


def test_bus_net_width_uses_each_instances_parameters(linked):  # D12 item 1
	_uart_port(linked, "paddr_i").wire.vectors = [_vector("BAUDRATE/300-1", "0")]  # 9600/300 = 32
	groups, _ = _bus_nets(linked)
	assert dict(groups[2][1])["bus_to_uart_PADDR"] == 32


def _side_port(linked, end, name):
	"""A port of the bus (end 0) or uart (end 1) side of bus_to_uart."""
	ports = _interconnection(linked, "bus_to_uart").endpoints[end].instance.component.model.ports
	return next(p for p in ports if p.name == name)


def test_bus_net_with_two_outputs_is_refused(linked):  # decision 5
	_side_port(linked, 1, "paddr_i").wire.direction = ipxact.Direction.OUT
	listed = "bus.m0_paddr_o \\(out\\), uart.paddr_i \\(out\\)"
	with pytest.raises(ValueError, match=f"'bus_to_uart_PADDR' joins two outputs \\({listed}\\)"):
		_bus_nets(linked)


def test_bus_net_with_two_inputs_is_refused(linked):  # decision 5
	_side_port(linked, 0, "m0_paddr_o").wire.direction = ipxact.Direction.IN
	listed = "bus.m0_paddr_o \\(in\\), uart.paddr_i \\(in\\)"
	with pytest.raises(ValueError, match=f"'bus_to_uart_PADDR' joins two inputs \\({listed}\\)"):
		_bus_nets(linked)


@pytest.mark.parametrize("end, name", [(0, "m0_paddr_o"), (1, "paddr_i")])
def test_bus_net_with_an_inout_is_accepted(linked, end, name):  # decision 5
	_side_port(linked, end, name).wire.direction = ipxact.Direction.INOUT
	groups, _ = _bus_nets(linked)
	assert "bus_to_uart_PADDR" in dict(groups[2][1])


def _rename_instance(linked, old, new):
	"""Rename an instance, in the linked design's index and on the instance itself."""
	instance = linked.instances.pop(old)
	instance.instance_name = new
	linked.instances[new] = instance


def _rename_ad_hoc(linked, old, new):
	"""Rename an ad hoc connection, in the linked design and in the design as written."""
	linked.ad_hoc_connections[new] = linked.ad_hoc_connections.pop(old)
	next(a for a in linked.design.ad_hoc_connections if a.name == old).name = new


def test_bus_net_name_that_is_not_an_identifier_is_refused(linked):  # decision 2, D5
	_interconnection(linked, "cpu_to_bus").name = "cpu-to-bus"
	with pytest.raises(ValueError, match="bus net 'cpu-to-bus_PADDR' .* is not a legal"):
		_bus_nets(linked)


def test_bus_net_named_like_a_top_port_is_refused(linked):  # decision 2
	linked.component.model.ports.append(
		ipxact.Port(name="cpu_to_bus_PADDR", wire=ipxact.WirePort(direction=ipxact.Direction.IN))
	)
	with pytest.raises(ValueError, match="same name as top port 'cpu_to_bus_PADDR'"):
		_bus_nets(linked)


def test_bus_net_named_like_a_phantom_top_port_is_accepted(linked):  # decision 2
	phantom = ipxact.WirePort(direction=ipxact.Direction.PHANTOM)
	linked.component.model.ports.append(ipxact.Port(name="cpu_to_bus_PADDR", wire=phantom))
	_bus_nets(linked)


def test_bus_net_named_like_an_instance_is_refused(linked):  # decision 2
	_rename_instance(linked, "gpio", "cpu_to_bus_PADDR")
	with pytest.raises(ValueError, match="same name as instance 'cpu_to_bus_PADDR'"):
		_bus_nets(linked)


def test_bus_net_named_like_an_ad_hoc_net_is_refused(linked):  # decision 2
	_rename_ad_hoc(linked, "uart_irq_o_to_cpu_irq_i", "cpu_to_bus_PADDR")
	with pytest.raises(ValueError, match="same name as ad hoc net 'cpu_to_bus_PADDR'"):
		_bus_nets(linked)


def test_two_interconnections_with_one_name_are_refused(linked):  # xactflow does not check it
	_interconnection(linked, "debug_to_bus").name = "cpu_to_bus"
	with pytest.raises(ValueError, match="two interconnections named 'cpu_to_bus'"):
		_bus_nets(linked)


def test_two_bus_nets_with_one_name_are_refused(linked):  # decision 2
	_interconnection(linked, "debug_to_bus").name = "cpu_to"
	for end in (0, 1):
		port_map = next(m for m in _port_maps(linked, "cpu_to", end) if m.logical_port == "PADDR")
		port_map.logical_port = "bus_PADDR"  # cpu_to + bus_PADDR = cpu_to_bus + PADDR
	message = "'cpu_to_bus_PADDR' of interconnection 'cpu_to' has the same name as bus net"
	with pytest.raises(ValueError, match=message):
		_bus_nets(linked)


def _add_to_irq_connection(linked, port):
	"""Add a port of uart to the ad hoc connection from uart.irq_o to cpu.irq_i."""
	references = linked.ad_hoc_connections["uart_irq_o_to_cpu_irq_i"]
	uart = next(r for r in references if r.instance.instance_name == "uart")
	references.append(dataclasses.replace(uart, port=_uart_port(linked, port)))


def test_port_on_a_bus_net_and_in_an_ad_hoc_connection_is_refused(linked):  # decision 6
	_add_to_irq_connection(linked, "psel_i")
	message = (
		"port 'psel_i' of instance 'uart' is on bus net 'bus_to_uart_PSEL' .* and in ad hoc "
		"connection 'uart_irq_o_to_cpu_irq_i'"
	)
	with pytest.raises(ValueError, match=message):
		_bus_nets(linked)


def test_port_of_an_unconnected_bus_interface_may_be_wired_ad_hoc(linked):  # decision 6
	_add_to_irq_connection(linked, "psel_i")
	linked.interconnections.remove(_interconnection(linked, "bus_to_uart"))
	_, ports = _bus_nets(linked)
	assert "uart" not in ports
