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
