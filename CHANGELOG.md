# Changelog

## [Unreleased]

## [0.5] - 2018-03-13

### Changed
- splitting behaviour has changed: By default, a double ``split_char`` ("\_\_")
  indicates a new nested settings section. This allows environment variables to
  look more natural when they are describing nested settings. The option
  ``implicit_depth`` may be used to override this behaviour and have a single
  "\_" indicate a new nested section.
- ``max_depth`` parameter has been deprecated in favor of ``implicit_depth``
