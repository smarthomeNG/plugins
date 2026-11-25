# mcp sample config

A throwaway shng configuration for trying the `mcp` plugin from an MCP client such as Claude Code.
It has no modules, one logic and one item tree; `testbed.sh` swaps it in and out of `etc/`.

## Switch on and off

```sh
sample_config/testbed.sh on     # parks etc/{plugin,module,logic,logic_groups,admin}.yaml and etc/items/*.yaml as *.yamlx
                                # installs the sample config with a fresh token, prints the `claude mcp add` command
# start shng, run the command it printed, restart Claude Code, try the checks below
sample_config/testbed.sh off    # stop shng first; restores the parked files
```

`SHNG_ETC=<dir>` overrides the etc directory. The script refuses to run while `*.yamlx` files exist in it.

## Items and expected access

`default_access: none`, `inherit_rw_access: false`:

| Item | Access | Try |
|---|---|---|
| `mcpdemo.counter` | ro | `wait_for_change` returns within 15 s (the logic `mcp_ticker` increments it) |
| `mcpdemo.house.temperature`, `humidity` | ro (inherited from `mcpdemo`) | `set_item` -> `forbidden` |
| `mcpdemo.house.lamp` | rw, 5 writes/min | the 6th write within a minute -> `rate_limited` with `retry_after` |
| `mcpdemo.house.lamp.brightness_note` | ro (child of rw) | `set_item` -> `forbidden`; rw with `inherit_rw_access: true` |
| `mcpdemo.house.dimmer` | rw, has an `eval` | `set_item 150` reports the old value and `changed: false` (the eval applies it asynchronously); `get_item` then shows 100 |
| `mcpdemo.house.setpoint` | rw, no rate limit | any number of writes; `get_item detail=full` hides `api_token` and `knx_password` |
| `mcpdemo.house.mode` | rw (str) | `set_item` with a number is cast to text |
| `mcpdemo.zone`, `zone.a`, `zone.b` | rw on `zone`, children ro | as `brightness_note` |
| `mcpdemo.private`, `private.secret_level` | none | `get_item` -> `not_found`, same as for a missing item |
| `mcpdemo.private.exception` | rw | an explicit value on the item beats the `none` above it |
| `mcpdemo.typo` | none | `mcp_access: readwrite` is invalid and treated as `none` |
| `unmarked` | none | `list_items` does not show it; readable with `default_access: ro` |

Other checks:

- `set_item mcpdemo.house.lamp "maybe"` -> `invalid_value`; `null` -> `invalid_value`.
- `get_access_info` shows the effective settings and the log files.
- `list_items prefix=mcpdemo. limit=3`, then the returned cursor, pages through the tree.
- `list_schedulers` shows the `logics.mcp_ticker` cycle entry with its next run; `list_logics`, `list_plugins`,
  `get_threads`, `get_system_info` need no setup.
- `get_logs file=smarthome-warnings.log contains=mcp_ticker`: the password, the bearer token and `SN-4711`
  (from `log_redact`) come back as `***`; every 4th run also logs a traceback as part of one entry.
  `contains=hunter2` finds nothing. `level=ERROR` and `since=<ISO time>` filter.
- `set_item` results show `mcp:local` in `last_change_by` (`get_item detail=full`).

Edit `etc/plugin.yaml` and restart shng to try `default_access: ro`, `inherit_rw_access: true`, a smaller
`write_rate_limit`, or fewer `expose` groups (a call to a group that is not exposed -> `not_exposed`).
