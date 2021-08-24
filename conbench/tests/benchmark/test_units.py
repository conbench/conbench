from ...units import bytes_per_second_fmt, formatter_for_unit, items_per_second_fmt


def test_items_per_second_fmt():
    assert items_per_second_fmt(None, "i/s") is None
    assert items_per_second_fmt(0, "i/s") == "0 i/s"
    assert items_per_second_fmt(1, "i/s") == "1 i/s"
    assert items_per_second_fmt(1000, "i/s") == "1.000 K i/s"
    assert items_per_second_fmt(1000000, "i/s") == "1.000 M i/s"
    assert items_per_second_fmt(1000000000, "i/s") == "1.000 G i/s"


def test_bytes_per_second_fmt():
    assert bytes_per_second_fmt(None, "B/s") is None
    assert bytes_per_second_fmt(0, "B/s") == "0 B/s"
    assert bytes_per_second_fmt(1, "B/s") == "1 B/s"
    assert bytes_per_second_fmt(1024, "B/s") == "1.000 KiB/s"
    assert bytes_per_second_fmt(1048576, "B/s") == "1.000 MiB/s"
    assert bytes_per_second_fmt(1073741824, "B/s") == "1.000 GiB/s"
    assert bytes_per_second_fmt(1099511627776, "B/s") == "1.000 TiB/s"


def test_formatter_for_unit():
    assert formatter_for_unit("B/s")(None, "B/s") is None
    assert formatter_for_unit("i/s")(None, "i/s") is None
    assert formatter_for_unit("s")(None, "s") is None
    assert formatter_for_unit("B/s")(1024, "B/s") == "1.000 KiB/s"
    assert formatter_for_unit("i/s")(1024, "i/s") == "1.024 K i/s"
    assert formatter_for_unit("s")(1024, "s") == "1024.000 s"
