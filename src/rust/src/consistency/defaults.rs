use chrono::{DateTime, FixedOffset, Local, Timelike};

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

/// Local time, like the vault's Templater notes and the Python `set_default_date` fixer.
fn set_default_date(data: &mut ZettelData) {
    if is_missing(data, "date") {
        let now: DateTime<FixedOffset> = Local::now()
            .with_nanosecond(0)
            .expect("zero nanoseconds is always valid")
            .fixed_offset();
        data.metadata
            .insert("date".to_string(), YamlValue::DateTime(now));
    }
}

/// The id is the date's own wall clock (no conversion), like the Python `set_default_id` fixer.
fn set_default_id(data: &mut ZettelData) {
    if is_missing(data, "id") {
        if let Some(YamlValue::DateTime(dt)) = data.metadata.get("date") {
            let id_str = dt.format("%Y%m%d%H%M%S").to_string();
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
    use chrono::TimeZone;

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

    #[test]
    fn test_id_keeps_the_dates_own_offset() {
        let plus_two = FixedOffset::east_opt(2 * 3600).unwrap();
        let mut local = ZettelData::new();
        local.metadata.insert(
            "date".to_string(),
            YamlValue::DateTime(plus_two.with_ymd_and_hms(2024, 9, 13, 12, 0, 0).unwrap()),
        );
        let mut utc = ZettelData::new();
        utc.metadata.insert(
            "date".to_string(),
            YamlValue::DateTime(
                FixedOffset::east_opt(0)
                    .unwrap()
                    .with_ymd_and_hms(2024, 9, 13, 10, 0, 0)
                    .unwrap(),
            ),
        );

        set_missing_defaults(&mut local);
        set_missing_defaults(&mut utc);

        assert!(matches!(
            local.metadata.get("id"),
            Some(YamlValue::Int(20240913120000))
        ));
        assert!(matches!(
            utc.metadata.get("id"),
            Some(YamlValue::Int(20240913100000))
        ));
    }

    #[test]
    fn test_default_date_is_local_time_without_subseconds() {
        let mut data = ZettelData::new();
        set_missing_defaults(&mut data);

        let Some(YamlValue::DateTime(dt)) = data.metadata.get("date") else {
            panic!("date was not set");
        };
        assert_eq!(dt.nanosecond(), 0);
        assert_eq!(
            dt.offset(),
            &Local.offset_from_utc_datetime(&dt.naive_utc())
        );
        let expected_id = dt.format("%Y%m%d%H%M%S").to_string();
        assert!(matches!(
            data.metadata.get("id"),
            Some(YamlValue::Int(id)) if id.to_string() == expected_id
        ));
    }
}
