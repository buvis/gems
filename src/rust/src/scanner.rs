use std::collections::HashMap;
use std::fs;
use std::path::Path;

use rayon::prelude::*;
use serde::{Deserialize, Serialize};
use walkdir::WalkDir;

use crate::consistency;
use crate::migration;
use crate::parser;
use crate::types::{YamlValue, ZettelData};

/// Simple filter value for metadata eq matching.
#[derive(Debug, Clone)]
pub enum MetaFilterValue {
    Str(String),
    Bool(bool),
    Int(i64),
}

fn yaml_eq_filter(yaml: &YamlValue, filter: &MetaFilterValue) -> bool {
    match (yaml, filter) {
        (YamlValue::String(a), MetaFilterValue::Str(b)) => a == b,
        (YamlValue::Bool(a), MetaFilterValue::Bool(b)) => a == b,
        (YamlValue::Int(a), MetaFilterValue::Int(b)) => a == b,
        _ => false,
    }
}

fn metadata_matches(meta: &HashMap<String, YamlValue>, conditions: &[(String, MetaFilterValue)]) -> bool {
    conditions.iter().all(|(key, expected)| {
        meta.get(key).map_or(false, |actual| yaml_eq_filter(actual, expected))
    })
}

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

/// Like load_all but filters on metadata eq conditions after the pipeline.
/// Only returns entries where all conditions match.
pub fn load_filtered(
    directory: &str,
    extensions: &[String],
    conditions: &[(String, MetaFilterValue)],
) -> Result<Vec<ZettelData>, String> {
    let files = collect_files(directory, extensions)?;

    let results: Vec<Option<ZettelData>> = files
        .par_iter()
        .map(|path| {
            let mut data = match parser::parse_file(path) {
                Ok(d) => d,
                Err(e) => {
                    eprintln!("Warning: {}", e);
                    return None;
                }
            };
            process_zettel(&mut data);
            if metadata_matches(&data.metadata, conditions) {
                Some(data)
            } else {
                None
            }
        })
        .collect();

    Ok(results.into_iter().flatten().collect())
}

// ── Metadata cache ──────────────────────────────────────────────────────

const CACHE_VERSION: u8 = 1;

#[derive(Serialize, Deserialize)]
struct CacheEntry {
    mtime_secs: i64,
    mtime_nanos: u32,
    metadata: HashMap<String, YamlValue>,
    reference: HashMap<String, YamlValue>,
}

type Cache = HashMap<String, CacheEntry>;

fn load_cache(path: &Path) -> Cache {
    let bytes = match fs::read(path) {
        Ok(b) => b,
        Err(_) => return Cache::new(),
    };
    if bytes.is_empty() || bytes[0] != CACHE_VERSION {
        return Cache::new();
    }
    bincode::deserialize(&bytes[1..]).unwrap_or_default()
}

fn save_cache(path: &Path, cache: &Cache) {
    if let Some(parent) = path.parent() {
        let _ = fs::create_dir_all(parent);
    }
    let mut bytes = vec![CACHE_VERSION];
    if let Ok(encoded) = bincode::serialize(cache) {
        bytes.extend(encoded);
        let _ = fs::write(path, bytes);
    }
}

fn get_mtime(path: &Path) -> Option<(i64, u32)> {
    fs::metadata(path).ok().and_then(|m| {
        m.modified().ok().map(|t| {
            let dur = t.duration_since(std::time::UNIX_EPOCH).unwrap_or_default();
            (dur.as_secs() as i64, dur.subsec_nanos())
        })
    })
}

/// Two-phase cached load:
/// - Warm: trust cache, filter on cached metadata, full-parse only matches
/// - Cold: local-only walk+parse, build cache
pub fn load_cached(
    directory: &str,
    extensions: &[String],
    conditions: &[(String, MetaFilterValue)],
    cache_path: &str,
) -> Result<Vec<ZettelData>, String> {
    let cp = Path::new(cache_path);
    let cache = load_cache(cp);

    if cache.is_empty() {
        return load_cached_cold(directory, extensions, conditions, cp);
    }

    // Warm path: filter on cached metadata, no stat calls
    let match_paths: Vec<std::path::PathBuf> = cache
        .iter()
        .filter(|(_, entry)| metadata_matches(&entry.metadata, conditions))
        .map(|(path_str, _)| std::path::PathBuf::from(path_str))
        .collect();

    // Full-parse only matching files for sections
    let results: Vec<Option<ZettelData>> = match_paths
        .par_iter()
        .map(|path| {
            let mut data = match parser::parse_file(path) {
                Ok(d) => d,
                Err(e) => {
                    eprintln!("Warning: {}", e);
                    return None;
                }
            };
            process_zettel(&mut data);
            Some(data)
        })
        .collect();

    Ok(results.into_iter().flatten().collect())
}

/// Cold path: local-only walk (no symlink following), parse + build cache.
/// Cloud-synced dirs behind symlinks are picked up by background refresh_cache.
fn load_cached_cold(
    directory: &str,
    extensions: &[String],
    conditions: &[(String, MetaFilterValue)],
    cache_path: &Path,
) -> Result<Vec<ZettelData>, String> {
    let files = collect_files_opt(directory, extensions, false)?;

    let parsed: Vec<Option<(String, CacheEntry, Option<ZettelData>)>> = files
        .par_iter()
        .map(|path| {
            let mut data = match parser::parse_file(path) {
                Ok(d) => d,
                Err(e) => {
                    eprintln!("Warning: {}", e);
                    return None;
                }
            };
            process_zettel(&mut data);
            let key = path.to_string_lossy().to_string();
            let (secs, nanos) = get_mtime(path).unwrap_or((0, 0));
            let entry = CacheEntry {
                mtime_secs: secs,
                mtime_nanos: nanos,
                metadata: data.metadata.clone(),
                reference: data.reference.clone(),
            };
            let matched = if metadata_matches(&data.metadata, conditions) {
                Some(data)
            } else {
                None
            };
            Some((key, entry, matched))
        })
        .collect();

    let mut cache = Cache::with_capacity(parsed.len());
    let mut results = Vec::new();
    for item in parsed.into_iter().flatten() {
        let (key, entry, matched) = item;
        cache.insert(key, entry);
        if let Some(data) = matched {
            results.push(data);
        }
    }

    save_cache(cache_path, &cache);
    Ok(results)
}

/// Background cache refresh: walk directory, compare with existing cache, update.
/// Returns a summary string (empty if no changes).
pub fn refresh_cache(
    directory: &str,
    extensions: &[String],
    cache_path: &str,
) -> Result<String, String> {
    let cp = Path::new(cache_path);
    let old_cache = load_cache(cp);
    let files = collect_files(directory, extensions)?;

    let old_keys: std::collections::HashSet<&str> =
        old_cache.keys().map(|k| k.as_str()).collect();
    let new_keys: std::collections::HashSet<String> = files
        .iter()
        .map(|p| p.to_string_lossy().to_string())
        .collect();

    // Count new and deleted files
    let n_new = new_keys.iter().filter(|k| !old_keys.contains(k.as_str())).count();
    let n_deleted = old_keys.iter().filter(|k| !new_keys.contains(**k)).count();

    // Find stale files (mtime changed)
    let stale_or_new: Vec<&std::path::PathBuf> = files
        .iter()
        .filter(|p| {
            let key = p.to_string_lossy();
            match old_cache.get(key.as_ref()) {
                Some(entry) => {
                    let mtime = get_mtime(p);
                    match mtime {
                        Some((s, n)) => s != entry.mtime_secs || n != entry.mtime_nanos,
                        None => true,
                    }
                }
                None => true, // new file
            }
        })
        .collect();

    let n_modified = stale_or_new.len().saturating_sub(n_new);

    if n_new == 0 && n_deleted == 0 && n_modified == 0 {
        return Ok(String::new());
    }

    // Parse new/stale files in parallel
    let new_entries: Vec<Option<(String, CacheEntry)>> = stale_or_new
        .par_iter()
        .map(|path| {
            let mut data = match parser::parse_file(path) {
                Ok(d) => d,
                Err(e) => {
                    eprintln!("Warning: {}", e);
                    return None;
                }
            };
            process_zettel(&mut data);
            let key = path.to_string_lossy().to_string();
            let (secs, nanos) = get_mtime(path).unwrap_or((0, 0));
            Some((key, CacheEntry {
                mtime_secs: secs,
                mtime_nanos: nanos,
                metadata: data.metadata,
                reference: data.reference,
            }))
        })
        .collect();

    let mut cache = old_cache;
    for item in new_entries.into_iter().flatten() {
        cache.insert(item.0, item.1);
    }
    // Remove deleted
    cache.retain(|k, _| new_keys.contains(k));
    save_cache(cp, &cache);

    // Build summary
    let mut parts = Vec::new();
    if n_new > 0 {
        parts.push(format!("{} new", n_new));
    }
    if n_modified > 0 {
        parts.push(format!("{} modified", n_modified));
    }
    if n_deleted > 0 {
        parts.push(format!("{} deleted", n_deleted));
    }
    let summary = parts.join(", ");

    Ok(summary)
}

/// Collect file paths matching extensions from a directory tree.
fn collect_files(directory: &str, extensions: &[String]) -> Result<Vec<std::path::PathBuf>, String> {
    collect_files_opt(directory, extensions, true)
}

fn collect_files_opt(directory: &str, extensions: &[String], follow_links: bool) -> Result<Vec<std::path::PathBuf>, String> {
    let dir = Path::new(directory);
    if !dir.is_dir() {
        return Err(format!("Not a directory: {}", directory));
    }

    Ok(WalkDir::new(dir)
        .follow_links(follow_links)
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
