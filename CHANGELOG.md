# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog and this project follows semantic versioning for public APIs where applicable.

## [Unreleased]

## [0.2.0] - 2025-08-26
### Added
- CONTRIBUTING.md with development and PR guidelines
- Badges to README.md
- SECURITY.md with vulnerability reporting policy
- CHANGELOG.md

### Fixed
- Improved zstd compression implementation in GCSUploader.upload_json()
  - Removed unnecessary file I/O operations during compression
  - Fixed content type and encoding settings for compressed uploads
  - Unified upload logic for both compressed and uncompressed JSON
  - Added compression size logging for better observability

## [0.1.5] - 2025-08-23
### Added
- Support: Browser Use LLMType

[Unreleased]: https://github.com/ParadigmShift-AI-Corp/neurosim/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/ParadigmShift-AI-Corp/neurosim/releases/tag/v0.2.0
[0.1.5]: https://github.com/ParadigmShift-AI-Corp/neurosim/releases/tag/v0.1.5


