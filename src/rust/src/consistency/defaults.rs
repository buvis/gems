use chrono::{DateTime, FixedOffset, Local, Timelike, Utc};

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
    matches!(data.metadata.get(key), None | Some(YamlValue::Null))
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

/// The id is the UTC digits of the date, like the Python `set_default_id` fixer.
fn set_default_id(data: &mut ZettelData) {
    if is_missing(data, "id") {
        if let Some(YamlValue::DateTime(dt)) = data.metadata.get("date") {
            let id_str = dt.with_timezone(&Utc).format("%Y%m%d%H%M%S").to_string();
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
            if let Some(stripped) = heading.strip_prefix("# ") {
                stripped.to_string()
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
    use chrono::{TimeZone, Utc};

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
        data.metadata.insert(
            "title".to_string(),
            YamlValue::String("My title".to_string()),
        );

        set_missing_defaults(&mut data);

        assert_eq!(
            data.metadata.get("title").unwrap().as_str(),
            Some("My title")
        );
    }

    #[test]
    fn test_id_is_the_utc_digits_of_the_date() {
        let date = |offset_secs: i32, ymd: (i32, u32, u32), hms: (u32, u32, u32)| {
            FixedOffset::east_opt(offset_secs)
                .unwrap()
                .with_ymd_and_hms(ymd.0, ymd.1, ymd.2, hms.0, hms.1, hms.2)
                .unwrap()
        };
        let id_for = |dt: DateTime<FixedOffset>, null_id: bool| {
            let mut data = ZettelData::new();
            data.metadata
                .insert("date".to_string(), YamlValue::DateTime(dt));
            if null_id {
                data.metadata.insert("id".to_string(), YamlValue::Null);
            }
            set_missing_defaults(&mut data);
            data.metadata.get("id").and_then(|v| v.as_int())
        };
        let sept13 = (2024, 9, 13);

        // +02:00 12:00 and UTC 10:00 are the same instant: same UTC id.
        assert_eq!(id_for(date(2 * 3600, sept13, (12, 0, 0)), false), Some(20240913100000));
        assert_eq!(id_for(date(0, sept13, (10, 0, 0)), false), Some(20240913100000));
        // A negative offset moves the UTC digits forward, across midnight.
        let west = date(-5 * 3600 - 30 * 60, sept13, (22, 15, 0));
        assert_eq!(id_for(west, false), Some(20240914034500));
        // A 45-minute offset is converted exactly, not rounded.
        assert_eq!(id_for(date(20700, sept13, (12, 0, 0)), false), Some(20240913061500));
        // Another year, non-zero seconds, back across a year boundary.
        let nye = date(2 * 3600, (1999, 12, 31), (23, 59, 58));
        assert_eq!(id_for(nye, false), Some(19991231215958));
        // An explicit `id: null` counts as missing and gets the UTC digits.
        assert_eq!(id_for(date(2 * 3600, sept13, (12, 0, 0)), true), Some(20240913100000));
        assert_eq!(id_for(nye, true), Some(19991231215958));
    }

    #[test]
    fn test_existing_id_is_kept_over_the_utc_date_digits() {
        let mut data = ZettelData::new();
        data.metadata.insert(
            "date".to_string(),
            YamlValue::DateTime(
                FixedOffset::east_opt(2 * 3600)
                    .unwrap()
                    .with_ymd_and_hms(2024, 9, 13, 12, 0, 0)
                    .unwrap(),
            ),
        );
        data.metadata.insert("id".to_string(), YamlValue::Int(42));

        set_missing_defaults(&mut data);

        assert_eq!(data.metadata.get("id").and_then(|v| v.as_int()), Some(42));

        data.metadata
            .insert("id".to_string(), YamlValue::String("abc".to_string()));
        set_missing_defaults(&mut data);
        assert_eq!(data.metadata.get("id").and_then(|v| v.as_str()), Some("abc"));
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
        let expected_id = dt.with_timezone(&Utc).format("%Y%m%d%H%M%S").to_string();
        assert!(matches!(
            data.metadata.get("id"),
            Some(YamlValue::Int(id)) if id.to_string() == expected_id
        ));
    }
}
