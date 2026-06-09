import json
import sys
from io import StringIO
from unittest.mock import MagicMock, patch

import pytest

from netlab.output import StdoutOutput, FileOutput, HttpPostOutput, make_output


SAMPLE_EVENT = {"schema_version": "1.0", "event_type": "netlab.test", "severity": "info", "payload": {}}


# --- StdoutOutput ---

def test_stdout_output_emits_json(capsys):
    out = StdoutOutput()
    out.emit(SAMPLE_EVENT)
    captured = capsys.readouterr()
    assert json.loads(captured.out.strip()) == SAMPLE_EVENT


def test_stdout_output_flush(capsys):
    out = StdoutOutput()
    out.emit(SAMPLE_EVENT)
    out.flush()  # should not raise


# --- FileOutput ---

def test_file_output_writes_json(tmp_path):
    path = tmp_path / "events.jsonl"
    out = FileOutput(str(path))
    out.emit(SAMPLE_EVENT)
    out.flush()
    lines = path.read_text().strip().splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0]) == SAMPLE_EVENT


def test_file_output_appends_multiple(tmp_path):
    path = tmp_path / "events.jsonl"
    out = FileOutput(str(path))
    out.emit(SAMPLE_EVENT)
    out.emit({**SAMPLE_EVENT, "event_type": "netlab.test2"})
    out.flush()
    lines = path.read_text().strip().splitlines()
    assert len(lines) == 2
    assert json.loads(lines[1])["event_type"] == "netlab.test2"


# --- HttpPostOutput ---

def test_http_post_no_batching_posts_immediately():
    out = HttpPostOutput(url="http://fake", batch_size=1)
    with patch.object(out, "_post") as mock_post:
        out.emit(SAMPLE_EVENT)
        mock_post.assert_called_once_with(SAMPLE_EVENT)


def test_http_post_batches_until_threshold():
    out = HttpPostOutput(url="http://fake", batch_size=3)
    with patch.object(out, "_post") as mock_post:
        out.emit(SAMPLE_EVENT)
        out.emit(SAMPLE_EVENT)
        mock_post.assert_not_called()
        out.emit(SAMPLE_EVENT)
        mock_post.assert_called_once()
        # batch is a list when batch_size > 1
        call_arg = mock_post.call_args[0][0]
        assert isinstance(call_arg, list)
        assert len(call_arg) == 3


def test_http_post_flush_sends_remaining():
    out = HttpPostOutput(url="http://fake", batch_size=5)
    with patch.object(out, "_post") as mock_post:
        out.emit(SAMPLE_EVENT)
        out.emit(SAMPLE_EVENT)
        mock_post.assert_not_called()
        out.flush()
        mock_post.assert_called_once()
        assert len(mock_post.call_args[0][0]) == 2


def test_http_post_flush_empty_buffer_no_post():
    out = HttpPostOutput(url="http://fake", batch_size=1)
    with patch.object(out, "_post") as mock_post:
        out.flush()
        mock_post.assert_not_called()


def test_http_post_auth_header_stripped():
    out = HttpPostOutput(url="http://fake", auth_header="Authorization: Bearer mytoken")
    headers = out._build_headers()
    assert headers["Authorization"] == "Bearer mytoken"


def test_http_post_auth_header_plain():
    out = HttpPostOutput(url="http://fake", auth_header="Bearer mytoken")
    headers = out._build_headers()
    assert headers["Authorization"] == "Bearer mytoken"


def test_http_post_no_auth_header_empty():
    out = HttpPostOutput(url="http://fake")
    headers = out._build_headers()
    assert "Authorization" not in headers


def test_http_post_batch_size_minimum_one():
    out = HttpPostOutput(url="http://fake", batch_size=0)
    assert out.batch_size == 1


# --- make_output factory ---

def test_make_output_stdout():
    out = make_output("stdout")
    assert isinstance(out, StdoutOutput)


def test_make_output_file(tmp_path):
    path = tmp_path / "out.jsonl"
    out = make_output("file", path=str(path))
    assert isinstance(out, FileOutput)


def test_make_output_http_post():
    out = make_output("http_post", url="http://fake")
    assert isinstance(out, HttpPostOutput)


def test_make_output_http_post_batch_size():
    out = make_output("http_post", url="http://fake", batch_size=10)
    assert isinstance(out, HttpPostOutput)
    assert out.batch_size == 10


def test_make_output_unknown_raises():
    with pytest.raises(ValueError, match="Unknown output spec"):
        make_output("kafka")


def test_make_output_defaults_file_path(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    out = make_output("file")
    assert isinstance(out, FileOutput)
