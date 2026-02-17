use serde::{Deserialize, Serialize};
use std::collections::HashMap;

/// Mirror of Python's ZettelData value object.
/// Holds metadata, reference, and content sections parsed from a markdown file.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ZettelData {
    pub metadata: HashMap<String, YamlValue>,
    pub reference: HashMap<String, YamlValue>,
    pub sections: Vec<(String, String)>,
    pub file_path: Option<String>,
}

impl ZettelData {
    pub fn new() -> Self {
        Self {
            metadata: HashMap::new(),
            reference: HashMap::new(),
            sections: Vec::new(),
            file_path: None,
        }
    }
}

/// Dynamic YAML value type that can be converted to Python objects.
#[derive(Debug, Clone, Serialize, Deserialize, bincode::Encode, bincode::Decode)]
pub enum YamlValue {
    Null,
    Bool(bool),
    Int(i64),
    Float(f64),
    String(String),
    List(Vec<YamlValue>),
    DateTime(#[bincode(with_serde)] chrono::DateTime<chrono::FixedOffset>),
}

impl YamlValue {
    pub fn as_str(&self) -> Option<&str> {
        match self {
            YamlValue::String(s) => Some(s),
            _ => None,
        }
    }

    pub fn as_bool(&self) -> Option<bool> {
        match self {
            YamlValue::Bool(b) => Some(*b),
            _ => None,
        }
    }

    pub fn as_int(&self) -> Option<i64> {
        match self {
            YamlValue::Int(i) => Some(*i),
            _ => None,
        }
    }

    pub fn as_list(&self) -> Option<&Vec<YamlValue>> {
        match self {
            YamlValue::List(l) => Some(l),
            _ => None,
        }
    }

    pub fn as_list_mut(&mut self) -> Option<&mut Vec<YamlValue>> {
        match self {
            YamlValue::List(l) => Some(l),
            _ => None,
        }
    }
}

/// Convert serde_yml::Value into our YamlValue
impl From<serde_yml::Value> for YamlValue {
    fn from(v: serde_yml::Value) -> Self {
        match v {
            serde_yml::Value::Null => YamlValue::Null,
            serde_yml::Value::Bool(b) => YamlValue::Bool(b),
            serde_yml::Value::Number(n) => {
                if let Some(i) = n.as_i64() {
                    YamlValue::Int(i)
                } else if let Some(f) = n.as_f64() {
                    YamlValue::Float(f)
                } else {
                    YamlValue::Null
                }
            }
            serde_yml::Value::String(s) => {
                // Try parsing as datetime (serde_yml returns dates as strings)
                if let Ok(dt) = chrono::DateTime::parse_from_rfc3339(&s) {
                    YamlValue::DateTime(dt)
                } else if let Ok(dt) = chrono::DateTime::parse_from_str(&s, "%Y-%m-%d %H:%M:%S %z") {
                    YamlValue::DateTime(dt)
                } else if let Ok(dt) = chrono::DateTime::parse_from_str(&s, "%Y-%m-%d %H:%M:%S%z") {
                    YamlValue::DateTime(dt)
                } else if let Ok(dt) = chrono::NaiveDateTime::parse_from_str(&s, "%Y-%m-%d %H:%M:%S") {
                    let fixed = chrono::TimeZone::from_utc_datetime(&chrono::Utc, &dt);
                    YamlValue::DateTime(fixed.fixed_offset())
                } else if let Ok(dt) = chrono::NaiveDate::parse_from_str(&s, "%Y-%m-%d") {
                    let fixed = chrono::TimeZone::from_utc_datetime(
                        &chrono::Utc,
                        &dt.and_hms_opt(0, 0, 0).unwrap(),
                    );
                    YamlValue::DateTime(fixed.fixed_offset())
                } else if let Ok(dt) = chrono::NaiveDate::parse_from_str(s.trim_end_matches('T'), "%Y-%m-%d") {
                    // Handle truncated ISO format: "2025-01-30T"
                    let fixed = chrono::TimeZone::from_utc_datetime(
                        &chrono::Utc,
                        &dt.and_hms_opt(0, 0, 0).unwrap(),
                    );
                    YamlValue::DateTime(fixed.fixed_offset())
                } else {
                    YamlValue::String(s)
                }
            }
            serde_yml::Value::Sequence(seq) => {
                YamlValue::List(seq.into_iter().map(YamlValue::from).collect())
            }
            serde_yml::Value::Mapping(_) => {
                // Flatten mappings to string representation for now
                YamlValue::String(format!("{:?}", v))
            }
            serde_yml::Value::Tagged(tagged) => YamlValue::from(tagged.value),
        }
    }
}
