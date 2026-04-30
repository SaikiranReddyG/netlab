Purpose
-------
netlab emits codex-contract-compliant events to allow external consumers to ingest scenario lifecycle and scenario-specific telemetry. This document describes the JSON event schema, event types, severity ladder, and supported output destinations for netlab v0.1.0.

Event schema
------------
Each event is a single JSON object (line-delimited when emitted to stdout/file). Required fields:

- `schema_version`: "1.0"
- `timestamp`: RFC3339 with local offset, millisecond precision
- `source`: "netlab"
- `source_version`: netlab semantic version string
- `host`: hostname where netlab ran
- `event_type`: string (see Event types)
- `severity`: one of `info`, `low`, `medium`, `high`, `critical`
- `payload`: object with event-specific keys

Example:

```json
{
  "schema_version": "1.0",
  "timestamp": "2026-04-30T12:34:56.789+02:00",
  "source": "netlab",
  "source_version": "0.1.0",
  "host": "lab-host",
  "event_type": "netlab.scenario.started",
  "severity": "info",
  "payload": { "scenario": "arp_spoof" }
}
```

Event types
-----------
- `netlab.scenario.started` — emitted when a scenario run begins (severity `info`).
- `netlab.scenario.event` — scenario-internal milestone (severity `low`–`medium`).
- `netlab.scenario.completed` — scenario finished successfully (`info`).
- `netlab.scenario.aborted` — scenario aborted or failed mid-run (`high`).
- `netlab.lifecycle.warming_up` — after topology built, before scenario logic (`info`).
- `netlab.lifecycle.tearing_down` — teardown started (`info`).
- `netlab.lifecycle.clean` — teardown completed and host verified clean (`info`).
- `netlab.lifecycle.dirty` — teardown completed but residual state detected (`critical`).

Severity ladder
---------------
Allowed values: `info`, `low`, `medium`, `high`, `critical`.

Payload conventions
-------------------
- Lifecycle events include `{ "scenario": "<name>", "duration_seconds": <float> }` when applicable.
- Scenario events include `{ "scenario": "<name>", "step": "<label>", "details": { ... } }`.
- Aborted/dirty events include `{ "scenario": "<name>", "reason": "<short>", "residual_state": [...] }`.

Output destinations
-------------------
- `stdout`: one JSON object per line, flushed immediately.
- `file`: appended JSON Lines file.
- `http_post`: POSTs JSON to a configured URL. v0.1 posts each event individually; batching is deferred to v0.2.

Lifecycle
---------
Each invocation follows: preflight → optional `lab/setup.sh` → `netlab.scenarios` run → `lab/teardown.sh` → verify clean → exit. See `netlab run --help` and `netlab/cli.py` for runtime options.

What this is not
-----------------
netlab is not a daemon, not a multi-host simulator, and does not provide continuous metrics or hot reload. Each run is hermetic: setup → scenario → teardown → exit.
