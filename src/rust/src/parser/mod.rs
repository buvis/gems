pub mod back_matter;
pub mod enrichment;
pub mod front_matter;
pub mod key_normalizer;
pub mod sections;

use std::path::Path;

use crate::types::{YamlValue, ZettelData};

/// Parse markdown file content into ZettelData.
/// Mirrors MarkdownZettelFileParser.parse() + ZettelFileParser.from_file().
pub fn parse_content(content: &str) -> ZettelData {
    let mut data = ZettelData::new();

    let (metadata, remaining) = front_matter::extract_metadata(content);
    data.metadata = metadata
        .map(|m| key_normalizer::normalize_keys(m))
        .unwrap_or_default();

    let (reference, remaining) = back_matter::extract_reference(&remaining);
    data.reference = reference
        .map(|r| key_normalizer::normalize_keys(r))
        .unwrap_or_default();

    data.sections = sections::split_into_sections(&remaining);

    data
}

/// Parse a file from disk into ZettelData with filename enrichment.
pub fn parse_file(path: &Path) -> Result<ZettelData, String> {
    let content = std::fs::read_to_string(path)
        .map_err(|e| format!("Failed to read {}: {}", path.display(), e))?;

    let mut data = parse_content(&content);
    data.file_path = Some(path.to_string_lossy().to_string());

    // Enrich from filename (date, title) — only set defaults, don't override
    if let Some(stem) = path.file_stem().and_then(|s| s.to_str()) {
        if !data.metadata.contains_key("date") {
            if let Some(dt) = enrichment::date_from_filename(stem) {
                data.metadata.insert("date".to_string(), YamlValue::DateTime(dt));
            }
        }
        if !data.metadata.contains_key("title") {
            if let Some(title) = enrichment::title_from_filename(stem) {
                data.metadata.insert("title".to_string(), YamlValue::String(title));
            }
        }
    }

    Ok(data)
}

/// Parse a file with full fallback date resolution (fs creation date).
/// Used for single-file parse_file() Python API.
pub fn parse_file_with_fallback(path: &Path) -> Result<ZettelData, String> {
    let mut data = parse_file(path)?;

    // Fallback: if no date from filename, try filesystem creation date
    if !data.metadata.contains_key("date") {
        if let Some(dt) = enrichment::date_from_filesystem(path) {
            data.metadata.insert("date".to_string(), YamlValue::DateTime(dt));
        }
    }

    Ok(data)
}
