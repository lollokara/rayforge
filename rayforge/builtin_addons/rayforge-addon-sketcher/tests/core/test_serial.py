import json

import pytest
from sketcher.core import serial
from sketcher.core.serial import (
    DEFAULT_NAME,
    SerialCounter,
    advance,
    find_serial_names,
    load_counters,
    peek,
    save_counters,
)


@pytest.fixture(autouse=True)
def data_dir(tmp_path, monkeypatch):
    monkeypatch.setattr("rayforge.config.ADDON_DATA_DIR", tmp_path)
    return tmp_path


def test_format_with_padding_prefix_and_suffix():
    counter = SerialCounter(
        "batch", value=7, padding=4, prefix="SN-", suffix="/A"
    )
    assert counter.format() == "SN-0007/A"


def test_format_without_padding():
    assert SerialCounter("x", value=12).format() == "12"


def test_reset_returns_to_start():
    counter = SerialCounter("x", value=40, start=5)
    counter.reset()
    assert counter.value == 5


def test_peek_unknown_counter_uses_defaults_and_writes_nothing():
    assert peek("new") == "1"
    assert peek() == "1"
    assert not serial.serials_path().exists()


def test_peek_never_advances():
    save_counters({"a": SerialCounter("a", value=3)})
    assert [peek("a"), peek("a"), peek("a")] == ["3", "3", "3"]


def test_advance_adds_step_and_persists():
    save_counters({"a": SerialCounter("a", value=10, step=5)})
    advance(["a"])
    assert peek("a") == "15"
    assert load_counters()["a"].value == 15


def test_advance_counts_each_name_once():
    save_counters({"a": SerialCounter("a", value=1)})
    advance(["a", "a", "a"])
    assert load_counters()["a"].value == 2


def test_advance_creates_missing_counter():
    advance([DEFAULT_NAME])
    assert load_counters()[DEFAULT_NAME].value == 2


def test_advance_leaves_other_counters_alone():
    save_counters(
        {"a": SerialCounter("a", value=1), "b": SerialCounter("b", value=9)}
    )
    advance(["a"])
    assert load_counters()["b"].value == 9


def test_advance_with_no_names_writes_nothing():
    advance([])
    assert not serial.serials_path().exists()


def test_two_readers_share_the_file():
    """A second window that advanced in between is not overwritten."""
    save_counters({"a": SerialCounter("a", value=1)})
    advance(["a"])
    other_window = load_counters()
    other_window["a"].value += other_window["a"].step
    save_counters(other_window)

    advance(["a"])

    assert load_counters()["a"].value == 4


def test_counter_fields_round_trip():
    original = SerialCounter(
        "a", value=3, start=2, step=4, padding=5, prefix="P", suffix="S"
    )
    save_counters({"a": original})
    assert load_counters()["a"] == original


def test_unknown_keys_and_bad_entries_are_ignored():
    serial.serials_path().write_text(
        json.dumps(
            {
                "counters": [
                    {"name": "ok", "value": 4, "future": True},
                    {"name": "bad", "value": "seven"},
                    {"value": 3},
                    "garbage",
                ]
            }
        ),
        encoding="utf-8",
    )
    counters = load_counters()
    assert list(counters) == ["ok"]
    assert counters["ok"].value == 4


def test_peek_survives_corrupt_file():
    serial.serials_path().write_text("{ nope", encoding="utf-8")
    assert peek("a") == "1"


def test_advance_backs_up_corrupt_file(data_dir):
    serial.serials_path().write_text("{ nope", encoding="utf-8")

    advance(["a"])

    backup = data_dir / "sketcher" / "serials.json.bak"
    assert backup.read_text(encoding="utf-8") == "{ nope"
    assert load_counters()["a"].value == 2


def test_save_leaves_no_temp_file(data_dir):
    save_counters({"a": SerialCounter("a")})
    assert [p.name for p in (data_dir / "sketcher").iterdir()] == [
        "serials.json"
    ]


@pytest.mark.parametrize(
    "text, expected",
    [
        ("plain", set()),
        ("{serial()}", {DEFAULT_NAME}),
        ('{serial("batch")}', {"batch"}),
        ("{serial('a')} and {serial( \"b\" ):>8}", {"a", "b"}),
        ("SN {serial()} / {serial('x')}", {DEFAULT_NAME, "x"}),
        ("{serial_number}", set()),
        ("{myserial()}", set()),
    ],
)
def test_find_serial_names(text, expected):
    assert find_serial_names(text) == expected


def test_advance_keeps_older_backup(data_dir):
    path = serial.serials_path()
    path.write_text("{ first", encoding="utf-8")
    advance(["a"])
    path.write_text("{ second", encoding="utf-8")

    advance(["a"])

    folder = data_dir / "sketcher"
    assert (folder / "serials.json.bak").read_text() == "{ first"
    assert (folder / "serials.json.bak.1").read_text() == "{ second"
