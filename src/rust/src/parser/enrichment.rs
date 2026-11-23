use std::path::Path;

use chrono::{DateTime, FixedOffset, NaiveDateTime, TimeZone, Utc};
use regex::Regex;
use std::sync::LazyLock;

static DATETIME_RE: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"^(\d{14}|\d{12})").unwrap());

/// Extract date from filename stem (YYYYMMDDHHMMSS or YYYYMMDDHHMM).
///
/// The digits are read as UTC (same as the Python parser). Seconds 60-99 read as 59.
pub fn date_from_filename(stem: &str) -> Option<DateTime<FixedOffset>> {
    let caps = DATETIME_RE.captures(stem)?;
    let matched = caps.get(1)?.as_str();
    if !matched.is_ascii() {
        return None;
    }

    let clamped;
    let input = if matched.len() == 14 && matched[12..].parse::<u32>().is_ok_and(|s| s >= 60) {
        clamped = format!("{}59", &matched[..12]);
        clamped.as_str()
    } else {
        matched
    };

    for fmt in &["%Y%m%d%H%M%S", "%Y%m%d%H%M"] {
        if let Ok(naive) = NaiveDateTime::parse_from_str(input, fmt) {
            return Some(Utc.from_utc_datetime(&naive).fixed_offset());
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
        let capitalized = {
            let c = chars.next()?;
            c.to_uppercase().to_string() + chars.as_str()
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
    fn test_filename_digits_are_utc() {
        let dt = date_from_filename("20240115143022").unwrap();
        assert_eq!(dt.offset().local_minus_utc(), 0);
        assert_eq!(dt.naive_utc().format("%Y%m%d%H%M%S").to_string(), "20240115143022");

        let dt = date_from_filename("202407311759").unwrap();
        assert_eq!(dt.offset().local_minus_utc(), 0);
        assert_eq!(dt.naive_utc().format("%Y%m%d%H%M%S").to_string(), "20240731175900");

        // Another year, and a day of 12 or less (March 5, not May 3).
        for stem in ["19991231235958", "20240305101112"] {
            let dt = date_from_filename(stem).unwrap();
            assert_eq!(dt.offset().local_minus_utc(), 0, "stem {stem}");
            assert_eq!(dt.naive_utc().format("%Y%m%d%H%M%S").to_string(), stem);
        }
    }

    #[test]
    fn test_suffix_seconds_read_as_59() {
        let utc_digits = |stem: &str| {
            let dt = date_from_filename(stem).unwrap();
            assert_eq!(dt.offset().local_minus_utc(), 0, "stem {stem}");
            dt.naive_utc().format("%Y%m%d%H%M%S").to_string()
        };

        assert_eq!(utc_digits("20240115143060"), "20240115143059");
        assert_eq!(utc_digits("20240115143075 Note"), "20240115143059");
        assert_eq!(utc_digits("20240115143099"), "20240115143059");
        assert_eq!(utc_digits("20240115143059"), "20240115143059");
        for second in 0..=59 {
            let stem = format!("202401151430{second:02}");
            assert_eq!(utc_digits(&stem), stem);
        }
    }

    #[test]
    fn test_non_ascii_digit_stem_returns_none() {
        assert!(date_from_filename("20240115143\u{FF11}").is_none());
        assert!(date_from_filename("2024011514\u{FF13}0").is_none());
        assert!(date_from_filename("\u{FF12}0240115143022").is_none());
    }

    #[test]
    fn test_date_from_12digit_filename() {
        let dt = date_from_filename("202401151430").unwrap();
        assert_eq!(dt.format("%Y%m%d%H%M").to_string(), "202401151430");
    }

    #[test]
    fn test_no_date_in_filename() {
        assert!(date_from_filename("my-note").is_none());
        // Impossible calendar values give no date; they do not roll over.
        assert!(date_from_filename("20240230120000").is_none());
        assert!(date_from_filename("20241301120000").is_none());
        assert!(date_from_filename("20240115250000").is_none());
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
