"""D1: where the module name comes from. Each case changes the linked example."""
import copy

import pytest

from rtlgen import _module_name


def _model(linked):
	return linked.component.model


def _add_view(linked, module_name):
	"""A second view instantiating the design, through a component instantiation of its own."""
	model = _model(linked)
	view = copy.deepcopy(model.views[0])
	view.name = "second"
	view.component_instantiation_ref = "second_rtl"
	instantiation = copy.deepcopy(model.component_instantiations[0])
	instantiation.name = "second_rtl"
	instantiation.module_name = module_name
	model.views.append(view)
	model.component_instantiations.append(instantiation)


def test_the_example(linked):
	assert _module_name(linked) == "soc_a"


def test_no_containing_component_is_refused(linked):  # item 2
	linked.component = None
	with pytest.raises(ValueError, match="no component in the library holds design"):
		_module_name(linked)


def test_view_without_component_instantiation_ref_is_refused(linked):  # item 3
	_model(linked).views[0].component_instantiation_ref = None
	with pytest.raises(ValueError, match="has no componentInstantiationRef"):
		_module_name(linked)


def test_view_referring_to_a_missing_instantiation_is_refused(linked):  # item 3
	_model(linked).views[0].component_instantiation_ref = "nope"
	with pytest.raises(ValueError, match="'nope', which the component does not have"):
		_module_name(linked)


@pytest.mark.parametrize("missing", [None, ""])
def test_instantiation_without_module_name_is_refused(linked, missing):  # item 3
	_model(linked).component_instantiations[0].module_name = missing
	with pytest.raises(ValueError, match="has no moduleName"):
		_module_name(linked)


def test_two_views_with_the_same_name_are_accepted(linked):  # item 4
	_add_view(linked, "soc_a")
	assert _module_name(linked) == "soc_a"


def test_two_views_with_different_names_are_refused(linked):  # item 4
	_add_view(linked, "soc_b")
	with pytest.raises(ValueError, match="view 'hierarchical' gives 'soc_a', view 'second' gives 'soc_b'"):
		_module_name(linked)


@pytest.mark.parametrize("name", ["soc.a", "2soc", "soc-a", "soc a", "$soc"])
def test_name_of_bad_form_is_refused(linked, name):  # item 5
	_model(linked).component_instantiations[0].module_name = name
	with pytest.raises(ValueError, match="is not a legal SystemVerilog identifier"):
		_module_name(linked)


@pytest.mark.parametrize("name", ["_soc", "soc$a", "SoC_2"])
def test_name_of_good_form_is_accepted(linked, name):  # item 5
	_model(linked).component_instantiations[0].module_name = name
	assert _module_name(linked) == name


def test_keyword_is_not_checked_yet(linked):  # item 5, deferred
	_model(linked).component_instantiations[0].module_name = "module"
	assert _module_name(linked) == "module"


def test_no_view_instantiating_the_design_is_refused(linked):  # item 6
	_model(linked).views[0].design_instantiation_ref = None
	with pytest.raises(ValueError, match="no view of component .* instantiates design"):
		_module_name(linked)
