use std::path::Path;

use rayon::prelude::*;
use walkdir::WalkDir;

use crate::consistency;
use crate::migration;
use crate::parser;
use crate::types::{YamlValue, ZettelData};

/// Scan a directory for markdown files, parse all in parallel with migration + consistency.
/// Returns Vec of fully processed ZettelData.
pub fn load_all(directory: &str, extensions: &[String]) -> Result<Vec<ZettelData>, String> {
    let files = collect_files(directory, extensions)?;

    // Parse in parallel with rayon
    let results: Vec<Result<ZettelData, String>> = files
        .par_iter()
        .map(|path| {
            let mut data = parser::parse_file(path)?;
            process_zettel(&mut data);
            Ok(data)
        })
        .collect();

    // Collect results, skip errors
    let mut all_data = Vec::with_capacity(results.len());
    for result in results {
        match result {
            Ok(data) => all_data.push(data),
            Err(e) => eprintln!("Warning: {}", e),
        }
    }

    Ok(all_data)
}

/// Collect file paths matching extensions from a directory tree.
fn collect_files(directory: &str, extensions: &[String]) -> Result<Vec<std::path::PathBuf>, String> {
    let dir = Path::new(directory);
    if !dir.is_dir() {
        return Err(format!("Not a directory: {}", directory));
    }

    Ok(WalkDir::new(dir)
        .into_iter()
        .filter_map(|e| e.ok())
        .filter(|e| e.file_type().is_file())
        .filter(|e| {
            e.path()
                .extension()
                .and_then(|ext| ext.to_str())
                .map(|ext| extensions.iter().any(|x| x == ext))
                .unwrap_or(false)
        })
        .map(|e| e.into_path())
        .collect())
}

/// Check if ZettelData matches a query (case-insensitive).
/// Searches sections, title, and tags.
fn matches_query(data: &ZettelData, query_lower: &str) -> bool {
    // Search sections (heading + content)
    for (heading, content) in &data.sections {
        if heading.to_lowercase().contains(query_lower)
            || content.to_lowercase().contains(query_lower)
        {
            return true;
        }
    }

    // Search title
    if let Some(YamlValue::String(title)) = data.metadata.get("title") {
        if title.to_lowercase().contains(query_lower) {
            return true;
        }
    }

    // Search tags
    if let Some(YamlValue::List(tags)) = data.metadata.get("tags") {
        for tag in tags {
            if let YamlValue::String(t) = tag {
                if t.to_lowercase().contains(query_lower) {
                    return true;
                }
            }
        }
    }

    false
}

/// Full-text search: scan directory, parse in parallel, return matches.
/// Searches raw content first, only runs migration+consistency on matches.
pub fn search(directory: &str, query: &str, extensions: &[String]) -> Result<Vec<ZettelData>, String> {
    let files = collect_files(directory, extensions)?;
    let query_lower = query.to_lowercase();

    let results: Vec<Option<ZettelData>> = files
        .par_iter()
        .map(|path| {
            let mut data = match parser::parse_file(path) {
                Ok(d) => d,
                Err(_) => return None,
            };

            // Search on raw parsed data (before expensive pipeline)
            if !matches_query(&data, &query_lower) {
                return None;
            }

            // Only process matches
            process_zettel(&mut data);
            Some(data)
        })
        .collect();

    Ok(results.into_iter().flatten().collect())
}

/// Apply migration + consistency pipeline to parsed ZettelData.
/// Mirrors Zettel.replace_data() flow: consistency -> migrate -> consistency.
fn process_zettel(data: &mut ZettelData) {
    let is_project = data
        .metadata
        .get("type")
        .and_then(|v| v.as_str())
        .map(|t| t == "project" || t == "loop")
        .unwrap_or(false);

    // First pass: consistency + migration + consistency (matches Python flow)
    consistency::ensure_consistency(data);
    if is_project {
        consistency::ensure_project_consistency(data);
    }

    if is_project {
        migration::migrate_project(data);
    } else {
        migration::migrate(data);
    }

    consistency::ensure_consistency(data);
    if is_project {
        consistency::ensure_project_consistency(data);
    }
}
