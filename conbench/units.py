def items_per_second_fmt(value, unit):
    if value is None:
        return None
    if value < 1000:
        return "{} {}".format(value, unit)
    if value < 1000 ** 2:
        return "{:.3f} K {}".format(value / 1000, unit)
    if value < 1000 ** 3:
        return "{:.3f} M {}".format(value / 1000 ** 2, unit)
    else:
        return "{:.3f} G {}".format(value / 1000 ** 3, unit)


def bytes_per_second_fmt(value, unit):
    if value is None:
        return None
    if value < 1024:
        return "{} {}".format(value, unit)
    if value < 1024 ** 2:
        return "{:.3f} Ki{}".format(value / 1024, unit)
    if value < 1024 ** 3:
        return "{:.3f} Mi{}".format(value / 1024 ** 2, unit)
    if value < 1024 ** 4:
        return "{:.3f} Gi{}".format(value / 1024 ** 3, unit)
    else:
        return "{:.3f} Ti{}".format(value / 1024 ** 4, unit)


def fmt_unit(value, unit):
    return "{:.3f} {}".format(value, unit) if value is not None else None


def formatter_for_unit(unit):
    if unit == "B/s":
        return bytes_per_second_fmt
    elif unit == "i/s":
        return items_per_second_fmt
    else:
        return fmt_unit
