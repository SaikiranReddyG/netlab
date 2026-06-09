import sys
import json
import time
from typing import Optional

try:
	import requests  # type: ignore
except Exception:  # pragma: no cover - optional
	requests = None


class Output:
	def emit(self, event: dict) -> None:
		raise NotImplementedError()

	def flush(self) -> None:
		pass


class StdoutOutput(Output):
	def emit(self, event: dict) -> None:
		print(json.dumps(event), flush=True)

	def flush(self) -> None:
		sys.stdout.flush()


class FileOutput(Output):
	def __init__(self, path: str):
		# line-buffered
		self.f = open(path, "a", buffering=1)

	def emit(self, event: dict) -> None:
		self.f.write(json.dumps(event) + "\n")

	def flush(self) -> None:
		try:
			self.f.flush()
		except OSError as e:
			print(f"Warning: Failed to flush event file: {e}", file=sys.stderr)


class HttpPostOutput(Output):
	def __init__(
		self,
		url: str = "http://127.0.0.1:8765/events",
		timeout: int = 5,
		auth_header: Optional[str] = None,
		batch_size: int = 1,
	):
		self.url = url
		self.timeout = timeout
		self.auth_header = auth_header
		self.batch_size = max(1, batch_size)
		self._buffer: list = []

	def _build_headers(self) -> dict:
		headers: dict = {}
		if self.auth_header:
			auth_value = self.auth_header.replace("Authorization: ", "", 1).strip()
			headers["Authorization"] = auth_value
		return headers

	def _post(self, payload) -> None:
		body = json.dumps(payload).encode("utf-8")
		headers = self._build_headers()
		attempts = 0
		backoff = 0.5
		max_attempts = 5
		while attempts < max_attempts:
			attempts += 1
			try:
				if requests is None:
					from urllib.request import Request, urlopen
					req_headers = {"Content-Type": "application/json", **headers}
					req = Request(self.url, data=body, headers=req_headers)
					with urlopen(req, timeout=self.timeout) as resp:
						resp.read()
				else:
					requests.post(self.url, json=payload, timeout=self.timeout, headers=headers or None)
				return
			except Exception:
				time.sleep(backoff)
				backoff = min(backoff * 2, 5)
		print(f"Warning: Failed to POST after {max_attempts} attempts; events dropped", file=sys.stderr)

	def emit(self, event: dict) -> None:
		self._buffer.append(event)
		if len(self._buffer) >= self.batch_size:
			self.flush()

	def flush(self) -> None:
		if not self._buffer:
			return
		payload = self._buffer if self.batch_size > 1 else self._buffer[0]
		self._buffer = []
		self._post(payload)


class TeeOutput(Output):
	"""Write events to two outputs simultaneously."""

	def __init__(self, primary: Output, secondary: Output):
		self.primary = primary
		self.secondary = secondary

	def emit(self, event: dict) -> None:
		self.primary.emit(event)
		try:
			self.secondary.emit(event)
		except Exception:
			pass

	def flush(self) -> None:
		self.primary.flush()
		try:
			self.secondary.flush()
		except Exception:
			pass


def make_output(
	spec: str,
	url: Optional[str] = None,
	path: Optional[str] = None,
	auth_header: Optional[str] = None,
	batch_size: int = 1,
) -> Output:
	spec = (spec or "stdout").lower()
	if spec == "stdout":
		return StdoutOutput()
	elif spec == "file":
		return FileOutput(path or "events.jsonl")
	elif spec == "http_post":
		return HttpPostOutput(
			url or "http://127.0.0.1:8765/events",
			auth_header=auth_header,
			batch_size=batch_size,
		)
	else:
		raise ValueError(f"Unknown output spec: {spec}")

