use chrono::{DateTime, FixedOffset, TimeZone, Utc};

use crate::types::{YamlValue, ZettelData};

/// Set missing default values for metadata fields.
/// Mirrors ZettelConsistencyService.set_missing_defaults().
pub fn set_missing_defaults(data: &mut ZettelData) {
    set_default_date(data);
    set_default_id(data);
    set_default_title(data);
    set_default_type(data);
    set_default_tags(data);
    set_default_publish(data);
    set_default_processed(data);
}

fn is_missing(data: &ZettelData, key: &str) -> bool {
    match data.metadata.get(key) {
        None => true,
        Some(YamlValue::Null) => true,
        _ => false,
    }
}

fn set_default_date(data: &mut ZettelData) {
    if is_missing(data, "date") {
        let now: DateTime<FixedOffset> = Utc::now().fixed_offset();
        // Truncate to seconds (no microseconds)
        let truncated = Utc
            .timestamp_opt(now.timestamp(), 0)
            .unwrap()
            .fixed_offset();
        data.metadata
            .insert("date".to_string(), YamlValue::DateTime(truncated));
    }
}

fn set_default_id(data: &mut ZettelData) {
    if is_missing(data, "id") {
        if let Some(YamlValue::DateTime(dt)) = data.metadata.get("date") {
            let utc_dt = dt.with_timezone(&Utc);
            let id_str = utc_dt.format("%Y%m%d%H%M%S").to_string();
            if let Ok(id) = id_str.parse::<i64>() {
                data.metadata.insert("id".to_string(), YamlValue::Int(id));
            }
        }
    }
}

fn set_default_title(data: &mut ZettelData) {
    if is_missing(data, "title") {
        // Try extracting from first section heading
        let title = if let Some((heading, _)) = data.sections.first() {
            if heading.starts_with("# ") {
                heading[2..].to_string()
            } else {
                "Unknown title".to_string()
            }
        } else {
            "Unknown title".to_string()
        };
        data.metadata
            .insert("title".to_string(), YamlValue::String(title));
    }
}

fn set_default_type(data: &mut ZettelData) {
    if is_missing(data, "type") {
        data.metadata
            .insert("type".to_string(), YamlValue::String("note".to_string()));
    }
}

fn set_default_tags(data: &mut ZettelData) {
    if is_missing(data, "tags") {
        data.metadata
            .insert("tags".to_string(), YamlValue::List(Vec::new()));
    }
}

fn set_default_publish(data: &mut ZettelData) {
    if is_missing(data, "publish") {
        data.metadata
            .insert("publish".to_string(), YamlValue::Bool(false));
    }
}

fn set_default_processed(data: &mut ZettelData) {
    if is_missing(data, "processed") {
        data.metadata
            .insert("processed".to_string(), YamlValue::Bool(false));
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_sets_all_defaults() {
        let mut data = ZettelData::new();
        set_missing_defaults(&mut data);

        assert!(data.metadata.contains_key("date"));
        assert!(data.metadata.contains_key("id"));
        assert!(data.metadata.contains_key("title"));
        assert!(data.metadata.contains_key("type"));
        assert!(data.metadata.contains_key("tags"));
        assert!(data.metadata.contains_key("publish"));
        assert!(data.metadata.contains_key("processed"));
    }

    #[test]
    fn test_does_not_override_existing() {
        let mut data = ZettelData::new();
        data.metadata
            .insert("title".to_string(), YamlValue::String("My title".to_string()));

        set_missing_defaults(&mut data);

        assert_eq!(
            data.metadata.get("title").unwrap().as_str(),
            Some("My title")
        );
    }
}
