from solarbank_manager.models import BankValues, Measurement
from solarbank_manager.regulation import house_consumption_w


def test_house_consumption_with_import() -> None:
    assert house_consumption_w(300, 150, 80, 0) == 530


def test_house_consumption_with_export() -> None:
    assert house_consumption_w(400, 200, 0, 100) == 500


def test_measurement_house_consumption_never_negative() -> None:
    sample = Measurement(
        grid_import_w=0,
        grid_export_w=1000,
        banks=[
            BankValues(name="B14", ac_output_w=100),
            BankValues(name="B16", ac_output_w=100),
        ],
    )

    assert sample.house_consumption_w == 0
