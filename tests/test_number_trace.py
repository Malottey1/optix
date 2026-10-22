"""The dashboard's number tracer (tools/check_dashboard.untraced_numbers) catches invented numbers
and accepts numbers from the data, clock times and the language's decimal comma."""
from tools.check_dashboard import numbers_of, untraced_numbers

SRC = {"nums": {75.5, 1.0, 37.0, 2.0, 0.0}, "words": {"m_showcase_e00253", "NOR_07"},
       "timeline": {"duration_sec": 6081}}


def test_numbers_from_the_data_and_clock_times_pass():
    assert untraced_numbers("NOR hold 75.5% of passes, 1 of 37 reached the box. 44:54 · 45+1 · 2 – 0", SRC) == []
    assert untraced_numbers("NOR tienen el 75,5 % · m_showcase_e00253 · NOR_07", SRC) == []


def test_invented_numbers_and_ids_are_caught():
    assert untraced_numbers("xG 1.84 from 12 shots", SRC) == ["1.84", "12"]
    assert untraced_numbers("event m_showcase_e99999", SRC) == ["m_showcase_e99999"]
    assert untraced_numbers("99:99", SRC) != []


def test_numbers_of_ignores_the_decimal_mark():
    assert numbers_of("75.5% and 37") == numbers_of("75,5 % y 37")
