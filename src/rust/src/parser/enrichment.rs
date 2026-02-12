use std::path::Path;

use chrono::{DateTime, FixedOffset, NaiveDateTime, TimeZone, Utc};
use once_cell::sync::Lazy;
use regex::Regex;

static DATETIME_RE: Lazy<Regex> =
    Lazy::new(|| Regex::new(r"^(\d{14}|\d{12})").unwrap());

/// Extract date from filename stem (YYYYMMDDHHMMSS or YYYYMMDDHHMM).
pub fn date_from_filename(stem: &str) -> Option<DateTime<FixedOffset>> {
    let caps = DATETIME_RE.captures(stem)?;
    let matched = caps.get(1)?.as_str();

    for fmt in &["%Y%m%d%H%M%S", "%Y%m%d%H%M"] {
        if let Ok(naive) = NaiveDateTime::parse_from_str(matched, fmt) {
            let utc = Utc.from_utc_datetime(&naive);
            return Some(utc.fixed_offset());
        }
    }

    None
}

/// Extract title from filename stem by removing the datetime prefix.
pub fn title_from_filename(stem: &str) -> Option<String> {
    let stripped = DATETIME_RE.replace(stem, "");
    let title = stripped.replace('-', " ").trim().to_string();

    if title.is_empty() {
        None
    } else {
        let mut chars = title.chars();
        let capitalized = match chars.next() {
            Some(c) => c.to_uppercase().to_string() + chars.as_str(),
            None => return None,
        };
        Some(capitalized)
    }
}

/// Fallback: get date from filesystem creation time.
/// Used only for single-file parse (not bulk load).
pub fn date_from_filesystem(path: &Path) -> Option<DateTime<FixedOffset>> {
    let metadata = std::fs::metadata(path).ok()?;
    let systime = metadata.created().or_else(|_| metadata.modified()).ok()?;
    let duration = systime.duration_since(std::time::UNIX_EPOCH).ok()?;
    let secs = duration.as_secs() as i64;

    let dt = DateTime::from_timestamp(secs, 0)?;
    Some(dt.fixed_offset())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_date_from_14digit_filename() {
        let dt = date_from_filename("20240115143022").unwrap();
        assert_eq!(dt.format("%Y%m%d%H%M%S").to_string(), "20240115143022");
    }

    #[test]
    fn test_date_from_12digit_filename() {
        let dt = date_from_filename("202401151430").unwrap();
        assert_eq!(dt.format("%Y%m%d%H%M").to_string(), "202401151430");
    }

    #[test]
    fn test_no_date_in_filename() {
        assert!(date_from_filename("my-note").is_none());
    }

    #[test]
    fn test_title_from_filename_with_date() {
        let title = title_from_filename("20240115143022-my-note").unwrap();
        assert_eq!(title, "My note");
    }

    #[test]
    fn test_title_from_filename_date_only() {
        assert!(title_from_filename("20240115143022").is_none());
    }

    #[test]
    fn test_title_from_filename_no_date() {
        let title = title_from_filename("my-note").unwrap();
        assert_eq!(title, "My note");
    }
}
