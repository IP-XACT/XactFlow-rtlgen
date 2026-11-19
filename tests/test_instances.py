"""D4 and D5: each instance is written with the module its component names. Each case changes
the linked example's CPU."""
import copy

import ipxact
import pytest

from rtlgen import RtlExporter, _instance_lines, _instance_module_name

# Instance name -> module name, in the example's design order.
EXAMPLE_MODULES = {
	"cpu": "cpu",
	"bus": "apb_interconnect",
	"uart": "uart",
	"gpio": "gpio",
	"debug": "debug",
}


def _cpu(linked):
	return linked.instances["cpu"]


def _model(linked):
	return _cpu(linked).component.model


def _add_view(linked, module_name):
	"""A second view of the CPU, through a component instantiation of its own."""
	model = _model(linked)
	view = copy.deepcopy(model.views[0])
	view.name = "second"
	view.component_instantiation_ref = "second_inst"
	instantiation = copy.deepcopy(model.component_instantiations[0])
	instantiation.name = "second_inst"
	instantiation.module_name = module_name
	model.views.append(view)
	model.component_instantiations.append(instantiation)


def test_the_example(linked):
	modules = {name: _instance_module_name(i) for name, i in linked.instances.items()}
	assert list(modules.items()) == list(EXAMPLE_MODULES.items())


def test_the_example_lines(linked):  # design order, 2-space indent
	assert _instance_lines(linked) == "".join(
		f"  {module} {name} ();\n" for name, module in EXAMPLE_MODULES.items()
	)


def test_view_without_references_is_ignored(linked):  # item 1
	_model(linked).views.append(ipxact.View(name="docs"))
	assert _instance_module_name(_cpu(linked)) == "cpu"


@pytest.mark.parametrize("field", ["design_instantiation_ref", "design_configuration_instantiation_ref"])
def test_hierarchical_component_is_refused(linked, field):  # item 2
	setattr(_model(linked).views[0], field, "sub")
	with pytest.raises(ValueError, match="hierarchical components are not supported yet"):
		_instance_module_name(_cpu(linked))


def test_hierarchical_view_beside_an_rtl_view_is_refused(linked):  # item 2
	_model(linked).views.append(ipxact.View(name="hierarchical", design_instantiation_ref="sub"))
	with pytest.raises(ValueError, match="view 'hierarchical' of .* hierarchical components"):
		_instance_module_name(_cpu(linked))


def test_view_referring_to_a_missing_instantiation_is_refused(linked):  # item 3
	_model(linked).views[0].component_instantiation_ref = "nope"
	with pytest.raises(ValueError, match="'nope', which the component does not have"):
		_instance_module_name(_cpu(linked))


@pytest.mark.parametrize("missing", [None, ""])
def test_instantiation_without_module_name_is_refused(linked, missing):  # item 3
	_model(linked).component_instantiations[0].module_name = missing
	with pytest.raises(ValueError, match="has no moduleName"):
		_instance_module_name(_cpu(linked))


def test_no_view_with_component_instantiation_ref_is_refused(linked):  # item 4
	_model(linked).views[0].component_instantiation_ref = None
	with pytest.raises(ValueError, match="no view of component .* has a componentInstantiationRef"):
		_instance_module_name(_cpu(linked))


def test_no_model_is_refused(linked):  # item 4
	_cpu(linked).component.model = None
	with pytest.raises(ValueError, match="has a componentInstantiationRef"):
		_instance_module_name(_cpu(linked))


def test_two_views_with_the_same_name_are_accepted(linked):  # item 5
	_add_view(linked, "cpu")
	assert _instance_module_name(_cpu(linked)) == "cpu"


def test_two_views_with_different_names_are_refused(linked):  # item 5
	_add_view(linked, "cpu2")
	with pytest.raises(ValueError, match="view 'rtl_view' gives 'cpu', view 'second' gives 'cpu2'"):
		_instance_module_name(_cpu(linked))


@pytest.mark.parametrize("language", ["systemverilog", "SystemVerilog", " systemverilog ", None, ""])
def test_systemverilog_or_no_language_is_accepted(linked, language):  # item 6
	_model(linked).component_instantiations[0].language = language
	assert _instance_module_name(_cpu(linked)) == "cpu"


@pytest.mark.parametrize("language", ["verilog", "Verilog", "vhdl"])
def test_other_language_is_refused(linked, language):  # item 6
	_model(linked).component_instantiations[0].language = language
	with pytest.raises(ValueError, match=f"is in language '{language}': only SystemVerilog"):
		_instance_module_name(_cpu(linked))


def test_virtual_component_is_refused(linked):  # item 7
	_model(linked).component_instantiations[0].is_virtual = True
	with pytest.raises(ValueError, match="is virtual .* virtual components are not supported yet"):
		_instance_module_name(_cpu(linked))


@pytest.mark.parametrize("name", ["c.p.u", "2cpu", "cpu-0", "cpu 0"])
def test_module_name_of_bad_form_is_refused(linked, name):  # item 8, D5
	_model(linked).component_instantiations[0].module_name = name
	with pytest.raises(ValueError, match="module name .* is not a legal SystemVerilog identifier"):
		_instance_module_name(_cpu(linked))


@pytest.mark.parametrize("name", ["cpu.0", "0cpu", "cpu 0"])
def test_instance_name_of_bad_form_is_refused(linked, name):  # D5
	_cpu(linked).instance_name = name
	with pytest.raises(ValueError, match="instance name .* is not a legal SystemVerilog identifier"):
		_instance_lines(linked)


@pytest.mark.parametrize("name", ["_cpu", "cpu$1", "Cpu_2"])
def test_instance_name_of_good_form_is_accepted(linked, name):  # D5
	_cpu(linked).instance_name = name
	assert f"  cpu {name} ();\n" in _instance_lines(linked)


def test_refused_instance_writes_nothing(library, linked, tmp_path):
	linked.instances["uart"].component.model.component_instantiations[0].language = "vhdl"
	with pytest.raises(ValueError, match="language 'vhdl'"):
		RtlExporter().export(library, tmp_path)
	assert list(tmp_path.iterdir()) == []
