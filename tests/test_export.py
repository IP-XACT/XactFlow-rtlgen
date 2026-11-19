"""1a and 1b: the plugin is found, exports the example, and refuses what it cannot handle."""
import copy

import ipxact
import pytest
import xactflow
from xactflow import Library
from xactflow.cli import main

from conftest import EXPECTED_SOC_A
from rtlgen import RtlExporter


def test_xactflow_finds_the_plugin():
	assert xactflow.discover_exporters()["rtl"] is RtlExporter


def test_exports_the_example(library, tmp_path):
	RtlExporter().export(library, tmp_path)
	assert [p.name for p in tmp_path.iterdir()] == ["soc_a.sv"]
	assert (tmp_path / "soc_a.sv").read_text() == EXPECTED_SOC_A


def test_cli_exports_the_example(example, tmp_path):
	args = ["rtl", str(example.design_file), "--output", str(tmp_path)]
	for folder in example.libs:
		args += ["--lib", str(folder)]
	assert main(args) == 0
	assert (tmp_path / "soc_a.sv").read_text() == EXPECTED_SOC_A


def test_no_design_is_a_type_error(tmp_path):
	with pytest.raises(TypeError, match="needs a design"):
		RtlExporter().export(Library(), tmp_path)


def test_unknown_option_is_refused(library, tmp_path):
	with pytest.raises(ValueError, match="unknown options: foo"):
		RtlExporter().export(library, tmp_path, foo="1")


def test_two_designs_are_refused(library, tmp_path):
	other = copy.deepcopy(next(library.targets(ipxact.Design)))
	other.vlnv = ipxact.VLNV("example.org", "design", "other.design", "1.0")
	assert library.add(other, target=True)
	with pytest.raises(ValueError, match="one design at a time, got 2"):
		RtlExporter().export(library, tmp_path)
	assert list(tmp_path.iterdir()) == []


def test_design_configuration_is_refused(library, tmp_path):
	configuration = ipxact.DesignConfiguration(
		vlnv=ipxact.VLNV("example.org", "design", "soc_a.designcfg", "1.0"),
		design_ref=ipxact.VLNVRef("example.org", "design", "soc_a.design", "1.0"),
	)
	assert library.add(configuration, target=True)
	with pytest.raises(ValueError, match="design configurations are not supported yet"):
		RtlExporter().export(library, tmp_path)
	assert list(tmp_path.iterdir()) == []


def test_link_errors_are_refused(example, tmp_path):
	library = Library.scan(example.generated)  # no components, no bus definitions
	assert library.add_file(example.design_file, target=True)
	with pytest.raises(ValueError, match="does not link: componentInstance 'cpu'"):
		RtlExporter().export(library, tmp_path)
	assert list(tmp_path.iterdir()) == []
