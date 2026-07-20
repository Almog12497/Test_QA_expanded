import pytest
from src.testing.test_framework import AmmeterTestFramework


def test_framework_loads_config_successfully():
    fw = AmmeterTestFramework()
    assert "ammeters" in fw.config
    assert "testing" in fw.config


def test_framework_missing_config_raises_file_not_found():
    with pytest.raises(FileNotFoundError, match="Config file not found"):
        AmmeterTestFramework(config_path="nonexistent_path/config.yaml")


def test_ammeter_cfg_returns_port_and_command():
    fw = AmmeterTestFramework()
    cfg = fw._ammeter_cfg("greenlee")
    assert cfg["port"] == 5001
    assert "MEASURE_GREENLEE" in cfg["command"]


@pytest.mark.parametrize("name,expected_port", [
    ("greenlee", 5001),
    ("entes",    5002),
    ("circutor", 5003),
])
def test_ammeter_cfg_port(name, expected_port):
    cfg = AmmeterTestFramework()._ammeter_cfg(name)
    assert cfg["port"] == expected_port


def test_ammeter_cfg_unknown_type_raises_value_error():
    fw = AmmeterTestFramework()
    with pytest.raises(ValueError, match="Unknown ammeter type"):
        fw._ammeter_cfg("unknown_device")
