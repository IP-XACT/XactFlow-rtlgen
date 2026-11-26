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
