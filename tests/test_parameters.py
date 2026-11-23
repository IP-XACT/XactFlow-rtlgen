import copy

import pytest
import xactflow


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


def test_override_of_no_component_parameter_is_refused(linked):
	overrides = linked.instances["uart"].source.component_ref.config_element_values
	overrides["BAUDRATEX"] = copy.copy(overrides["BAUDRATE"])
	with pytest.raises(ValueError, match="overrides 'BAUDRATEX', which is not a parameter"):
		_instance_lines(linked)


def _add_uart_view(linked, baudrate):
	"""A second view of the UART, through an instantiation of its own giving BAUDRATE."""
	model = linked.instances["uart"].component.model
	view = copy.deepcopy(model.views[0])
	view.name = "sim_view"
	view.component_instantiation_ref = "uart_sim"
	instantiation = copy.deepcopy(model.component_instantiations[0])
	instantiation.name = "uart_sim"
	instantiation.module_parameters[0].value.value = baudrate
	model.views.append(view)
	model.component_instantiations.append(instantiation)


def test_views_with_different_module_parameters_are_refused(linked):
	_add_uart_view(linked, "19200")
	with pytest.raises(ValueError, match="give different module parameters"):
		_instance_lines(linked)


def test_views_with_the_same_module_parameters_are_accepted(linked):
	_add_uart_view(linked, "BAUDRATE")
	assert "    .BAUDRATE(9600)\n" in _instance_lines(linked)


@pytest.mark.parametrize("text", ["NOPE", '"fast"'])
def test_value_that_cannot_be_worked_out_is_refused(linked, text):
	overrides = linked.instances["uart"].source.component_ref.config_element_values
	overrides["BAUDRATE"].value = text
	with pytest.raises(ValueError, match="instance 'uart': module parameter 'BAUDRATE'") as caught:
		_instance_lines(linked)
	assert isinstance(caught.value.__cause__, xactflow.ExpressionError)
