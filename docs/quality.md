# Quality assessment

This is a self-assessment against all 54 Core Integration Quality Scale rules. Marketplace classifies this project as **Custom**; it has no official Platinum award. Custom import, default-catalog acceptance and Core grading are separate reviews.

The automated suite enforces >95% line coverage in every module and strict typing. This assessment does not imply that physical food delivery, battery operation or every hardware unit has been verified. See [validation scope](validation.md).

| Rule | Assessment | Evidence / reason |
| --- | --- | --- |
| `action-setup` | Implemented | __init__.async_setup registers the action once; tests/test_lifecycle.py. |
| `appropriate-polling` | Implemented | 30-second coordinator reads; MCU owns schedules; README Daily use. |
| `brands` | Implemented | Original brand assets bundled inside custom_components/pet_feeder_local/brand. |
| `common-modules` | Implemented | Shared const.py, api.py, coordinator.py and entity.py. |
| `config-flow` | Implemented | Validated GUI flow, stable unique ID and duplicate checks; tests/test_config_flow.py reaches 100% line coverage. |
| `config-flow-test-coverage` | Implemented | Validated GUI flow, stable unique ID and duplicate checks; tests/test_config_flow.py reaches 100% line coverage. |
| `dependency-transparency` | Implemented | Manifest declares runtime integration dependencies; README explains the included client and test requirements. |
| `docs-actions` | Implemented | README and docs/actions.md, docs/camera.md, docs/validation.md document this rule. |
| `docs-conditions` | Exempt | No integration-specific conditions; README and docs/actions.md explain standard HA state conditions. |
| `docs-high-level-description` | Implemented | README and docs/actions.md, docs/camera.md, docs/validation.md document this rule. |
| `docs-installation-instructions` | Implemented | README and docs/actions.md, docs/camera.md, docs/validation.md document this rule. |
| `docs-removal-instructions` | Implemented | README and docs/actions.md, docs/camera.md, docs/validation.md document this rule. |
| `docs-triggers` | Exempt | No integration-specific triggers; README and docs/actions.md explain standard HA state triggers. |
| `entity-event-setup` | Implemented | CoordinatorEntity manages callbacks on entity add/remove; real HA lifecycle/unload test. |
| `entity-unique-id` | Implemented | FeederEntity provides stable identity, translated entity keys and shared DeviceInfo; all six platforms tested in HA. |
| `has-entity-name` | Implemented | FeederEntity provides stable identity, translated entity keys and shared DeviceInfo; all six platforms tested in HA. |
| `runtime-data` | Implemented | FeederConfigEntry = ConfigEntry[FeederCoordinator]; typed runtime_data. |
| `test-before-configure` | Implemented | Validated GUI flow, stable unique ID and duplicate checks; tests/test_config_flow.py reaches 100% line coverage. |
| `test-before-setup` | Implemented | Entry setup validates the API and device identity before first refresh; setup error tests. |
| `unique-config-entry` | Implemented | Validated GUI flow, stable unique ID and duplicate checks; tests/test_config_flow.py reaches 100% line coverage. |
| `action-exceptions` | Implemented | Translated HomeAssistantError / ServiceValidationError for setup/actions; all exception paths tested. |
| `config-entry-unloading` | Implemented | CoordinatorEntity manages callbacks on entity add/remove; real HA lifecycle/unload test. |
| `docs-configuration-parameters` | Implemented | README and docs/actions.md, docs/camera.md, docs/validation.md document this rule. |
| `docs-installation-parameters` | Implemented | README and docs/actions.md, docs/camera.md, docs/validation.md document this rule. |
| `entity-unavailable` | Implemented | Coordinator availability plus MCU/feeding gate; API failure/recovery and frontend tests. |
| `integration-owner` | Implemented | @e2equiel is the manifest codeowner. |
| `log-when-unavailable` | Implemented | DataUpdateCoordinator logs failure/recovery transitions; repeated-error test verifies one failure log. |
| `parallel-updates` | Implemented | PARALLEL_UPDATES=0 on all platforms; coordinator serializes writes. |
| `reauthentication-flow` | Implemented | Token/address/restream update validates unchanged device identity and preserves entities; tested. |
| `test-coverage` | Implemented | tools/check_coverage.py enforces >95% line coverage in each production module, not just total coverage. |
| `devices` | Implemented | FeederEntity provides stable identity, translated entity keys and shared DeviceInfo; all six platforms tested in HA. |
| `diagnostics` | Implemented | Allowlisted diagnostics omit credentials, addresses, identity, meal times and video; tested. |
| `discovery` | Implemented | SSDP manifest/flow validates local discovery and updates known LAN addresses; flow tests plus firmware description. |
| `discovery-update-info` | Implemented | SSDP manifest/flow validates local discovery and updates known LAN addresses; flow tests plus firmware description. |
| `docs-data-update` | Implemented | README and docs/actions.md, docs/camera.md, docs/validation.md document this rule. |
| `docs-examples` | Implemented | README and docs/actions.md, docs/camera.md, docs/validation.md document this rule. |
| `docs-known-limitations` | Implemented | README and docs/actions.md, docs/camera.md, docs/validation.md document this rule. |
| `docs-supported-devices` | Implemented | README and docs/actions.md, docs/camera.md, docs/validation.md document this rule. |
| `docs-supported-functions` | Implemented | README and docs/actions.md, docs/camera.md, docs/validation.md document this rule. |
| `docs-troubleshooting` | Implemented | README and docs/actions.md, docs/camera.md, docs/validation.md document this rule. |
| `docs-use-cases` | Implemented | README and docs/actions.md, docs/camera.md, docs/validation.md document this rule. |
| `dynamic-devices` | Exempt | Each entry represents one fixed feeder; no runtime-discovered child devices. |
| `entity-category` | Implemented | Optional MCU sensor is a connectivity diagnostic disabled by default; primary controls retain normal defaults. |
| `entity-device-class` | Implemented | Optional MCU sensor is a connectivity diagnostic disabled by default; primary controls retain normal defaults. |
| `entity-disabled-by-default` | Implemented | Optional MCU sensor is a connectivity diagnostic disabled by default; primary controls retain normal defaults. |
| `entity-translations` | Implemented | English translations for all six entity platforms, and icons.json for custom icons. |
| `exception-translations` | Implemented | Translated HomeAssistantError / ServiceValidationError for setup/actions; all exception paths tested. |
| `icon-translations` | Implemented | English translations for all six entity platforms, and icons.json for custom icons. |
| `reconfiguration-flow` | Implemented | Token/address/restream update validates unchanged device identity and preserves entities; tested. |
| `repair-issues` | Implemented | MCU issue appears and clears after recovery; real HA lifecycle test. |
| `stale-devices` | Exempt | The only device has the same lifetime as its config entry; no child devices can disappear. |
| `async-dependency` | Implemented | Included protocol client uses asynchronous aiohttp I/O with an HA-injected ClientSession. |
| `inject-websession` | Implemented | Included protocol client uses asynchronous aiohttp I/O with an HA-injected ClientSession. |
| `strict-typing` | Implemented | mypy strict=true passes every production Python module. |

The included protocol client is not released separately on PyPI. A future Core proposal may require splitting it into a maintained external package and will need independent review.

Sources: [Core Quality Scale](https://contributors.home-assistant.io/core/quality-scale/), [rule definitions](https://contributors.home-assistant.io/core/quality-scale/rules/), [Marketplace integration requirements](https://contributors.home-assistant.io/marketplace/guides/integrations/).
