from rtlgen import _instance_lines


def test_ports_in_component_order(linked):
	linked.ad_hoc_connections = dict(reversed(list(linked.ad_hoc_connections.items())))
	lines = _instance_lines(linked)
	assert lines.index(".irq_i(") < lines.index(".debug_req_i(")


def test_connection_to_a_top_port_is_left_out(linked):
	assert ".clk_i(" not in _instance_lines(linked)
