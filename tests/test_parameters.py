import copy

import pytest


from rtlgen import _instance_lines


def _baudrate(linked):
	return linked.instances["uart"].component.model.component_instantiations[0].module_parameters[0]


@pytest.mark.parametrize("usage_type", ["typed", None])
def test_typed_baudrate(linked, usage_type):
	_baudrate(linked).usage_type = usage_type
	assert "    .BAUDRATE(9600)\n" in _instance_lines(linked)


@pytest.mark.parametrize("usage_type", ["nontyped", "runtime"])
def test_nontyped_baudrate(linked, usage_type):
	_baudrate(linked).usage_type = usage_type
	with pytest.raises(ValueError, match=f"usageType '{usage_type}'"):
		_instance_lines(linked)


def test_illegal_module_parameter_name(linked):
	_baudrate(linked).name = "2BAUD"
	with pytest.raises(ValueError, match="'2BAUD'"):
		_instance_lines(linked)


def test_duplicate_module_parameter(linked):
	parameters = linked.instances["uart"].component.model.component_instantiations[0].module_parameters
	parameters.append(copy.copy(_baudrate(linked)))
	with pytest.raises(ValueError, match="'BAUDRATE' twice"):
		_instance_lines(linked)
