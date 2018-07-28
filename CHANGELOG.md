# Changelog

## [Unreleased]

### Removed

- Remove deprecated `max_depth` option for `EnvParser`/`Settings`.  Use `implicit_depth` instead.
- Removed unneeded (and undocumented) features:
  - Filtering (error-prone and undocumented)
  - Dynamic preparsers (should now be handled through subclassing)
  - Ordering of source loading (should now be handled through subclassing)
  - Remove hard dependency on toml (if no serialization libraries like toml or
    yaml are installed, will fall back to json).
  - Remove unneeded `logtools` module.

### Fixed

- #13 : Update fragments (separate files) are now preprocessed separately.
  "from_file" variables can no longer override subsequent file settings.

### Added

- Add serialization to json and yaml when generating configurations.
- Allow "from_file" modules to be parsed recursively (if a from_file setting is
  set to a json/yaml/toml file, it's contents will be parsed as a settings file
  instead of a simple string)
- Add debug logging which settings attributes were set.

## [0.6] - 2018-04-23

### Added

- [#9](https://github.com/daviskirk/climatecontrol/pull/9): Add temporary_changes method to Settings object
- [#10](https://github.com/daviskirk/climatecontrol/pull/10): Add better logging on setup


## [0.5] - 2018-03-13

### Changed
- splitting behaviour has changed: By default, a double ``split_char`` ("\_\_")
  indicates a new nested settings section. This allows environment variables to
  look more natural when they are describing nested settings. The option
  ``implicit_depth`` may be used to override this behaviour and have a single
  "\_" indicate a new nested section.
- ``max_depth`` parameter has been deprecated in favor of ``implicit_depth``
