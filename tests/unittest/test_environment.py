import os
import runpy
from pathlib import Path

import pytest

from conftest import clean_environ


@pytest.fixture(params=["unittest", "pro"])
def environment_fixture(request):
    if request.param == "unittest":
        return clean_environ.__wrapped__
    path = Path(__file__).parents[1] / "pro" / "conftest.py"
    return runpy.run_path(str(path))["clean_environ"].__wrapped__


def test_clean_environ_preserves_unrelated_variables(monkeypatch, environment_fixture):
    # Background servers may read the native environment while this fixture runs.
    monkeypatch.setenv("CURL_CFFI_TEST_UNRELATED", "keep")
    monkeypatch.setenv("http_proxy", "http://example.invalid")
    changes = []
    putenv = os.putenv
    unsetenv = os.unsetenv

    def tracked_putenv(key, value):
        changes.append(os.fsdecode(key))
        putenv(key, value)

    def tracked_unsetenv(key):
        changes.append(os.fsdecode(key))
        unsetenv(key)

    with monkeypatch.context() as spy:
        spy.setattr(os, "putenv", tracked_putenv)
        spy.setattr(os, "unsetenv", tracked_unsetenv)
        fixture = environment_fixture()
        next(fixture)
        try:
            assert "http_proxy" not in os.environ
            assert os.environ["CURL_CFFI_TEST_UNRELATED"] == "keep"
        finally:
            next(fixture, None)

    assert "CURL_CFFI_TEST_UNRELATED" not in changes
    assert os.environ["http_proxy"] == "http://example.invalid"


@pytest.mark.parametrize("key", ["HTTP_PROXY", "http_proxy", "hTtP_pRoXy"])
def test_clean_environ_filters_proxy_case(monkeypatch, environment_fixture, key):
    monkeypatch.setenv(key, "http://example.invalid")
    fixture = environment_fixture()
    next(fixture)
    try:
        assert key not in os.environ
    finally:
        next(fixture, None)
    assert os.environ[key] == "http://example.invalid"


def test_clean_environ_restores_changes(monkeypatch, environment_fixture):
    monkeypatch.setenv("CURL_CFFI_TEST_CHANGED", "original")
    monkeypatch.setenv("CURL_CFFI_TEST_DELETED", "original")
    monkeypatch.delenv("CURL_CFFI_TEST_ADDED", raising=False)
    fixture = environment_fixture()
    next(fixture)
    try:
        os.environ["CURL_CFFI_TEST_CHANGED"] = "changed"
        del os.environ["CURL_CFFI_TEST_DELETED"]
        os.environ["CURL_CFFI_TEST_ADDED"] = "added"
    finally:
        next(fixture, None)
    assert os.environ["CURL_CFFI_TEST_CHANGED"] == "original"
    assert os.environ["CURL_CFFI_TEST_DELETED"] == "original"
    assert "CURL_CFFI_TEST_ADDED" not in os.environ
