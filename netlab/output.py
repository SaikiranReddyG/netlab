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
	def __init__(self, url: str = "http://127.0.0.1:8765/events", timeout: int = 5):
		self.url = url
		self.timeout = timeout

	def emit(self, event: dict) -> None:
		body = json.dumps(event).encode("utf-8")
		# Simple per-event POST with retry/backoff
		attempts = 0
		backoff = 0.5
		max_attempts = 5
		while attempts < max_attempts:
			attempts += 1
			try:
				if requests is None:
					# fallback to urllib
					from urllib.request import Request, urlopen

					req = Request(self.url, data=body, headers={"Content-Type": "application/json"})
					with urlopen(req, timeout=self.timeout) as resp:
						resp.read()
				else:
					resp = requests.post(self.url, json=event, timeout=self.timeout)
					resp.raise_for_status()
				return
			except Exception as e:
				time.sleep(backoff)
				backoff = min(backoff * 2, 5)
		# final failure -- log and drop
		print(f"Warning: Failed to POST event after {max_attempts} attempts; event dropped", file=sys.stderr)


def make_output(spec: str, url: Optional[str] = None, path: Optional[str] = None) -> Output:
	spec = (spec or "stdout").lower()
	if spec == "stdout":
		return StdoutOutput()
	elif spec == "file":
		return FileOutput(path or "events.jsonl")
	elif spec == "http_post":
		return HttpPostOutput(url or "http://127.0.0.1:8765/events")
	else:
		raise ValueError(f"Unknown output spec: {spec}")

