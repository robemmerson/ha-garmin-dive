# Changelog

## [0.3.3](https://github.com/robemmerson/ha-garmin-dive/compare/v0.3.2...v0.3.3) (2026-05-04)


### Bug Fixes

* **photos:** tolerate per-photo failures and surface only verified URLs ([9baaef6](https://github.com/robemmerson/ha-garmin-dive/commit/9baaef6bdaa0b7a61d717bd760a06ae8a79d9226))
* **photos:** tolerate per-photo failures and surface only verified URLs ([511611c](https://github.com/robemmerson/ha-garmin-dive/commit/511611c5991051a0fa9193adc96836dfeddd6e91))

## [0.3.2](https://github.com/robemmerson/ha-garmin-dive/compare/v0.3.1...v0.3.2) (2026-05-03)


### Bug Fixes

* **sensor:** surface all dive years via _unrecorded_attributes ([d359e6b](https://github.com/robemmerson/ha-garmin-dive/commit/d359e6b3d83eb041d6c2dd0d702ecb1ad45d2d9f))
* **sensor:** surface all dive years via _unrecorded_attributes ([d5af55b](https://github.com/robemmerson/ha-garmin-dive/commit/d5af55bc3c8d4d7ec7e933c912a00509462fc882))

## [0.3.1](https://github.com/robemmerson/ha-garmin-dive/compare/v0.3.0...v0.3.1) (2026-05-03)


### Bug Fixes

* address HA runtime errors from production deployment ([97f9773](https://github.com/robemmerson/ha-garmin-dive/commit/97f9773956f734b419dec7ca8c8d7ec478514df0))

## [0.3.0](https://github.com/robemmerson/ha-garmin-dive/compare/v0.2.0...v0.3.0) (2026-05-03)


### Features

* **photos:** wire dive-photo gallery via PlayerProfile GraphQL ([6c53d8a](https://github.com/robemmerson/ha-garmin-dive/commit/6c53d8aac647687a529b305f0a221b682e111822))

## [0.2.0](https://github.com/robemmerson/ha-garmin-dive/compare/v0.1.0...v0.2.0) (2026-05-03)


### Features

* add integration skeleton, manifest, and constants ([613294a](https://github.com/robemmerson/ha-garmin-dive/commit/613294a88a70e2fdb4a7a9085194edfc807030a8))
* **api:** add devices, tags, gear-summary, and gear-detail endpoints ([fd9b5cd](https://github.com/robemmerson/ha-garmin-dive/commit/fd9b5cdb7736115defd6bc7638e691af0281eca1))
* **api:** add GraphQL POST helper and dive-photos wrapper ([d26919f](https://github.com/robemmerson/ha-garmin-dive/commit/d26919ff8e5dfd319434e1982d8b2677340d468b))
* **api:** audience exchange, social profile, and dive-token refresh ([86d5ed4](https://github.com/robemmerson/ha-garmin-dive/commit/86d5ed4e37af48ea94d79399c5d08d28a7329310))
* **api:** GarminDiveClient with dive-summary endpoint ([7413974](https://github.com/robemmerson/ha-garmin-dive/commit/7413974b8d6b3804843e874c269bdffac442565b))
* **auth:** GarminDiveAuth with ha-garmin wrap, audience exchange, token refresh ([d492e9f](https://github.com/robemmerson/ha-garmin-dive/commit/d492e9fb304786f934054ef5ad65792aaa40fb57))
* **binary_sensor:** service_due and new_dive_available sensors ([da39697](https://github.com/robemmerson/ha-garmin-dive/commit/da39697b13a8c5b2c9c25a8f32f63f9e47bbfab5))
* **brand:** add HACS placeholder brand assets ([362cbc2](https://github.com/robemmerson/ha-garmin-dive/commit/362cbc2dc2aca81ae88cec2a8fdba24b0423f6d6))
* **button:** manual refresh button ([dc3e6c2](https://github.com/robemmerson/ha-garmin-dive/commit/dc3e6c21ea419a34ed4a400277d9893e2bfae851))
* **calendar:** expose each dive as a calendar event ([922c54e](https://github.com/robemmerson/ha-garmin-dive/commit/922c54eae375e4138e0bf3b63666176cb20bc3cb))
* **config_flow:** user/MFA/reauth flow + options flow ([6349f6f](https://github.com/robemmerson/ha-garmin-dive/commit/6349f6fb1ab27eaa2f68c54e864348dc3a52ccb6))
* **coordinator:** CoordinatorData DTO and build_data orchestration ([9b9a3a1](https://github.com/robemmerson/ha-garmin-dive/commit/9b9a3a13007f3a2a76bdbb80a7ea0deb6dcaca51))
* **coordinator:** GarminDiveCoordinator with new-dive and service-due events ([b0dcd0a](https://github.com/robemmerson/ha-garmin-dive/commit/b0dcd0a3441634d5f1cc566f86923a523a058371))
* **coordinator:** integrate photo cache for gear and dive photos ([b5c00f3](https://github.com/robemmerson/ha-garmin-dive/commit/b5c00f376820e124a904f88e808bfca0aa6ea6fb))
* **diagnostics:** redacted config-entry diagnostics ([826243a](https://github.com/robemmerson/ha-garmin-dive/commit/826243a5581ac871c1726a47b5cd52af9891fd57))
* **entity:** base classes for account-scoped and sub-device entities ([8fdd965](https://github.com/robemmerson/ha-garmin-dive/commit/8fdd965ae6d016721eef0d4e5397268fba09c250))
* full async_setup_entry, runtime_data, and services ([855832c](https://github.com/robemmerson/ha-garmin-dive/commit/855832cbf61a0c7b6b980ae06b1f181d19b1ded9))
* **gear:** pure delta-fetch and service-status flip helpers ([8312ce6](https://github.com/robemmerson/ha-garmin-dive/commit/8312ce64c1ebc5b9e8f220e1e34e145594c732bd))
* **i18n:** strings, English translations, and icons ([af19913](https://github.com/robemmerson/ha-garmin-dive/commit/af1991368ba28c81b4a0ba43c1d9bdb33ab25795))
* **photos:** local photo cache with idempotent downloads ([90d2ab4](https://github.com/robemmerson/ha-garmin-dive/commit/90d2ab4136d748371806ed1982b77aecaf776622))
* **sensor:** account-level last-dive, totals, and depth/time sensors ([1b57b1e](https://github.com/robemmerson/ha-garmin-dive/commit/1b57b1e458ba8dfa6e6a7e38a9e9590dd032a78c))
* **sensor:** dive_log_year timeline sensor, tag breakdown, gear count ([3110721](https://github.com/robemmerson/ha-garmin-dive/commit/3110721deb07c0318edb0132c974f62ac9959397))
* **sensor:** per-dive-computer sub-devices and diagnostic sensors ([177b076](https://github.com/robemmerson/ha-garmin-dive/commit/177b076e9b7ab0815b7d52ccd0ff4ec6f7cabc3b))
* **sensor:** per-gear-item service, usage, and purchase sensors ([a08a6ab](https://github.com/robemmerson/ha-garmin-dive/commit/a08a6ab663b80640b147a77be4f4cf15051109cf))


### Bug Fixes

* **auth:** asyncio lock around refresh; tolerate missing refresh_token ([576c84a](https://github.com/robemmerson/ha-garmin-dive/commit/576c84a764a7a5e8a00ac22cb36a2c8fdd36827c))
* **ci:** manifest key order + codespell hass ignore ([202b242](https://github.com/robemmerson/ha-garmin-dive/commit/202b242a7497eb31a786d2a5b11f9c141545ec87))
* **deps:** split freezegun onto its own line in requirements_dev.txt ([bfb64c0](https://github.com/robemmerson/ha-garmin-dive/commit/bfb64c0085fe7470556f1c77e05a9c1e977fa9a4))
* pre-merge hardening (events, services unload, diagnostics test) ([c30bf54](https://github.com/robemmerson/ha-garmin-dive/commit/c30bf5455abca3d4cd5d7e75a0d056821c3376e0))
* **security,deps:** release-workflow heredoc, account-id collision, deps pins, e2e test ([dfe4368](https://github.com/robemmerson/ha-garmin-dive/commit/dfe4368b457a01b4cc6ad6a0107816682de3d00a))
* **security:** SHA-pin actions, clear ConfigFlow password, revoke on removal ([e180496](https://github.com/robemmerson/ha-garmin-dive/commit/e1804967389076cd48b382726ae2b303054dfc41))
* swap deprecated garth for ha-garmin ([d346923](https://github.com/robemmerson/ha-garmin-dive/commit/d346923751bec95cbe88206b96a4c29da3bff66a))
* **types:** address mypy strict findings across the codebase ([6ce56d0](https://github.com/robemmerson/ha-garmin-dive/commit/6ce56d0e51c602d22596b7f54e3af93da410e10e))


### Documentation

* 2h poll default, add average_depth, set repo metadata ([9745ce8](https://github.com/robemmerson/ha-garmin-dive/commit/9745ce8b80f36fbc850f132983f3cf801b058dc9))
* add dashboard examples and service-due automation recipe ([5ce568f](https://github.com/robemmerson/ha-garmin-dive/commit/5ce568f6cf4d4b6841f6f8129f850d2da8f3f8f4))
* add full implementation plan ([75551b1](https://github.com/robemmerson/ha-garmin-dive/commit/75551b1d412b6f5f09ff8a258ae6291ec1dbf97d))
* add HACS metadata and README skeleton ([895c251](https://github.com/robemmerson/ha-garmin-dive/commit/895c2512001cf5d6445484c643f7eeba092c3943))
* design spec for ha-garmin-dive integration ([bded648](https://github.com/robemmerson/ha-garmin-dive/commit/bded648d25b75de3e96ca96db1faf6cd5b52a88c))
