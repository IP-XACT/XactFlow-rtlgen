import ipxact
import pytest

from rtlgen import RtlExporter, _ad_hoc_nets, _instance_lines


def _port(linked, instance, port_name):
	"""A port of an instance's component."""
	return next(p for p in linked.instances[instance].component.model.ports if p.name == port_name)


def _set_range(linked, instance, port_name, left, right):
	"""Give a port of an instance's component the range [left:right]."""
	_port(linked, instance, port_name).wire.vectors = [
		ipxact.Vector(left=ipxact.Expression(value=left), right=ipxact.Expression(value=right))
	]


def test_ports_in_component_order(linked):
	linked.ad_hoc_connections = dict(reversed(list(linked.ad_hoc_connections.items())))
	lines = _instance_lines(linked)
	assert lines.index(".irq_i(") < lines.index(".debug_req_i(")


def test_connection_to_a_top_port_is_left_out(linked):
	assert ".clk_i(" not in _instance_lines(linked)


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
