import ipxact
import pytest

from conftest import EXPECTED_SOC_A
from rtlgen import RtlExporter, _ad_hoc_nets, _top_port_lines


def _top_port(linked, port_name):
	"""A port of the containing component."""
	return next(p for p in linked.component.model.ports if p.name == port_name)


def _vector(left, right):
	return ipxact.Vector(left=ipxact.Expression(value=left), right=ipxact.Expression(value=right))


def test_top_ports_in_component_order(linked):  # the header lines of EXPECTED_SOC_A
	header = EXPECTED_SOC_A.split("module soc_a (\n", 1)[1].split("\n);\n", 1)[0]
	assert _top_port_lines(linked) == header.split(",\n")


def test_phantom_top_port_is_left_out(linked):
	_top_port(linked, "clk_i").wire.direction = ipxact.Direction.PHANTOM
	lines = _top_port_lines(linked)
	assert len(lines) == 11
	assert not any(line.endswith(" clk_i") for line in lines)


def test_phantom_top_port_named_like_an_instance_is_accepted(linked):
	port = _top_port(linked, "clk_i")
	port.wire.direction = ipxact.Direction.PHANTOM
	port.name = "cpu"
	assert len(_top_port_lines(linked)) == 11


@pytest.mark.parametrize("left, right", [("16", "1"), ("0", "15")])
def test_top_port_range_keeps_its_bounds(linked, left, right):
	_top_port(linked, "gpio_i").wire.vectors = [_vector(left, right)]
	assert f"  input wire [{left}:{right}] gpio_i" in _top_port_lines(linked)


def test_non_wire_top_port_is_refused(linked):
	_top_port(linked, "clk_i").wire = None
	with pytest.raises(ValueError, match="not a wire port"):
		_top_port_lines(linked)


def test_top_port_array_is_refused(linked):
	_top_port(linked, "clk_i").arrays = [
		ipxact.ArrayBound(left=ipxact.Expression(value="3"), right=ipxact.Expression(value="0"))
	]
	with pytest.raises(ValueError, match="an array"):
		_top_port_lines(linked)


def test_top_port_with_several_vectors_is_refused(linked):
	_top_port(linked, "gpio_i").wire.vectors.append(_vector("3", "0"))
	with pytest.raises(ValueError, match="2 vectors"):
		_top_port_lines(linked)


def test_top_port_name_that_is_not_an_identifier_is_refused(linked):
	_top_port(linked, "clk_i").name = "clk i"
	with pytest.raises(ValueError, match="not a legal SystemVerilog identifier"):
		_top_port_lines(linked)


def test_top_port_named_like_an_instance_is_refused(linked):
	_top_port(linked, "clk_i").name = "cpu"
	with pytest.raises(ValueError, match="same name as an instance"):
		_top_port_lines(linked)


def test_module_without_ports_has_no_parentheses(library, linked, tmp_path):  # decision 12
	linked.component.model.ports = []
	for connection in linked.design.ad_hoc_connections:
		if connection.external_port_references:  # the instance ports it reaches would be open
			for reference in linked.ad_hoc_connections[connection.name]:  # (step 7a)
				ports = reference.instance.component.model.ports
				ports[:] = [port for port in ports if port.name != reference.port.name]
	linked.design.ad_hoc_connections = [
		a for a in linked.design.ad_hoc_connections if not a.external_port_references
	]
	RtlExporter().export(library, tmp_path)
	assert "\nmodule soc_a;\n" in (tmp_path / "soc_a.sv").read_text()


@pytest.mark.parametrize(
	"left, right, message",
	[("7", "0", "different widths"), ("0", "15", "opposite bit orders")],
)
def test_top_port_that_does_not_match_its_net_is_refused(linked, left, right, message):
	_top_port(linked, "gpio_i").wire.vectors = [_vector(left, right)]
	with pytest.raises(ValueError, match=f"{message} .*top port gpio_i \\[{left}:{right}\\]"):
		_ad_hoc_nets(linked)


def test_top_port_with_other_bound_of_the_same_width_is_accepted(linked):
	_top_port(linked, "gpio_i").wire.vectors = [_vector("16", "1")]
	assert _ad_hoc_nets(linked)[1]["gpio"]["gpio_i"] == "gpio_i"
