"""Step 7a: an instance port that no connection reaches. Each case adds a port, or a bus
interface, to the linked example's UART."""
import copy

import ipxact
import pytest

from rtlgen import _instance_lines


def _uart(linked):
	return linked.instances["uart"].component


def _add_port(linked, name, direction):
	"""A port of the UART that nothing connects, second in its port list (after clk_i)."""
	port = ipxact.Port(name=name, wire=ipxact.WirePort(direction=direction))
	_uart(linked).model.ports.insert(1, port)
	return port


@pytest.mark.parametrize(
	"name, direction", [("spare_o", ipxact.Direction.OUT), ("pad_io", ipxact.Direction.INOUT)]
)
def test_open_output_or_inout_is_written_open(linked, name, direction):  # decisions 1 and 3
	_add_port(linked, name, direction)
	assert f"uart (\n    .clk_i(clk_i),\n    .{name}(),\n    .rst_ni(rst_ni),\n" in _instance_lines(linked)


def test_open_input_is_refused(linked):  # decision 2
	_add_port(linked, "spare_i", ipxact.Direction.IN)
	with pytest.raises(ValueError, match="port 'spare_i' of instance 'uart' is an input that no connection"):
		_instance_lines(linked)


def test_open_input_with_a_default_is_refused(linked):  # the default question: Rule C
	port = _add_port(linked, "spare_i", ipxact.Direction.IN)
	port.wire.drivers = [ipxact.Driver(default_value=ipxact.Expression(value="0"))]
	with pytest.raises(ValueError, match="port 'spare_i' of instance 'uart' is an input that no connection"):
		_instance_lines(linked)


def test_open_phantom_port_is_left_out(linked):  # decision 4
	_add_port(linked, "feed", ipxact.Direction.PHANTOM)
	assert "feed" not in _instance_lines(linked)


def test_open_non_wire_port_is_refused(linked):  # decision 4
	_add_port(linked, "spare_o", ipxact.Direction.OUT).wire = None
	with pytest.raises(ValueError, match="port 'spare_o' of instance 'uart' is not a wire port"):
		_instance_lines(linked)


def test_open_array_port_is_refused(linked):  # decision 4
	port = _add_port(linked, "spare_o", ipxact.Direction.OUT)
	port.arrays = [
		ipxact.ArrayBound(left=ipxact.Expression(value="3"), right=ipxact.Expression(value="0"))
	]
	with pytest.raises(ValueError, match="port 'spare_o' of instance 'uart' is an array"):
		_instance_lines(linked)


def test_open_port_with_a_bad_name_is_refused(linked):  # D5
	_add_port(linked, "spare-o", ipxact.Direction.OUT)
	with pytest.raises(ValueError, match="port name 'spare-o' of instance 'uart' is not a legal"):
		_instance_lines(linked)


def _add_bus_interface(linked, connection_required):
	"""A copy of the UART's bus interface that no interconnection uses."""
	bus_interfaces = _uart(linked).bus_interfaces
	bus_interface = copy.deepcopy(bus_interfaces[0])
	bus_interface.name = "spare_apb"
	bus_interface.connection_required = connection_required
	bus_interfaces.append(bus_interface)


def test_unused_bus_interface_that_requires_a_connection_is_refused(linked):  # decision 5
	_add_bus_interface(linked, connection_required=True)
	message = "bus interface 'spare_apb' of instance 'uart' requires a connection"
	with pytest.raises(ValueError, match=message):
		_instance_lines(linked)


def test_unused_bus_interface_is_accepted(linked):  # decision 5: connectionRequired false
	_add_bus_interface(linked, connection_required=False)
	_instance_lines(linked)


def test_used_bus_interface_that_requires_a_connection_is_accepted(linked):  # decision 5
	_uart(linked).bus_interfaces[0].connection_required = True
	_instance_lines(linked)
