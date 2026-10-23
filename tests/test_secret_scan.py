"""The secret scanner finds planted secrets (built at run time, so this file holds none) and the
tracked tree is clean."""
from tools import secret_scan as S


def test_planted_secrets_are_found():
    key = "AKIA" + "ABCDEFGHIJKLMNOP"
    pem = "-----BEGIN " + "RSA PRIVATE KEY-----"
    az = "api_key = '" + "0123456789abcdef" * 2 + "'"
    conn = "InstrumentationKey=" + "12345678-1234-1234-1234-123456789abc"
    hits = S.scan_text("x", "\n".join([key, pem, az, conn]))
    assert {h.split(": ", 1)[1] for h in hits} >= {"aws access key", "private key", "azure openai key",
                                                    "instrumentation key"}


def test_the_all_zero_test_key_is_allowed():
    assert S.scan_text("x", "InstrumentationKey=" + "0" * 8 + "-0000-0000-0000-" + "0" * 12) == []


def test_tracked_tree_is_clean():
    assert S.tracked() == []
