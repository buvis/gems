use std::collections::HashMap;

use once_cell::sync::Lazy;
use regex::Regex;

use crate::types::YamlValue;

static METADATA_RE: Lazy<Regex> =
    Lazy::new(|| Regex::new(r"(?s)---\n(.*?)\n---").unwrap());

/// Match tag/tags lines with inline values (not YAML list form).
/// Uses `[ \t]*` instead of `\s*` to avoid matching across newlines.
static TAG_LINE_RE: Lazy<Regex> =
    Lazy::new(|| Regex::new(r"(?m)^(?:tag|tags):[ \t]*(\S.*)$").unwrap());

/// Extract front matter YAML from markdown content.
/// Returns (parsed metadata, content with front matter removed).
pub fn extract_metadata(content: &str) -> (Option<HashMap<String, YamlValue>>, String) {
    let Some(caps) = METADATA_RE.captures(content) else {
        return (None, content.to_string());
    };

    let raw_front = caps.get(1).unwrap().as_str();
    let preprocessed = normalize_tags(raw_front);

    let yaml_val: serde_yaml::Value = match serde_yaml::from_str(&preprocessed) {
        Ok(v) => v,
        Err(_) => return (None, content.to_string()),
    };

    let metadata = yaml_to_map(yaml_val);
    let without = content.replacen(caps.get(0).unwrap().as_str(), "", 1);

    (Some(metadata), without)
}

/// Preprocess tag/tags lines: normalize brackets, commas, hashes into YAML list.
fn normalize_tags(text: &str) -> String {
    TAG_LINE_RE
        .replace_all(text, |caps: &regex::Captures| {
            let key_line = caps.get(0).unwrap().as_str();
            let key = key_line.split(':').next().unwrap();
            let tags_part = caps.get(1).unwrap().as_str();

            // Remove unsafe chars
            let cleaned = tags_part
                .replace('[', "")
                .replace(']', "")
                .replace(", ", " ")
                .replace(',', " ");

            // Remove hashes and split
            let tags: Vec<&str> = cleaned
                .split_whitespace()
                .map(|t| t.trim_start_matches('#'))
                .collect();

            format!("{}: [{}]", key, tags.join(", "))
        })
        .to_string()
}

/// Convert a serde_yaml::Value (expected Mapping) into our HashMap<String, YamlValue>.
fn yaml_to_map(val: serde_yaml::Value) -> HashMap<String, YamlValue> {
    let mut map = HashMap::new();

    if let serde_yaml::Value::Mapping(mapping) = val {
        for (k, v) in mapping {
            if let serde_yaml::Value::String(key) = k {
                map.insert(key, YamlValue::from(v));
            }
        }
    }

    map
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_extract_simple_front_matter() {
        let content = "---\nid: 42\ntitle: Simple test note\ndate: 2024-01-15 10:30:00 +00:00\ntype: note\ntags:\n  - testing\n  - parity\npublish: true\nprocessed: false\n---\n\n## Content\n\nThis is a simple test note.\n";
        let (meta, remaining) = extract_metadata(content);
        assert!(meta.is_some(), "Front matter should be parsed");
        let meta = meta.unwrap();
        assert_eq!(meta.get("id").and_then(|v| v.as_int()), Some(42));
        assert_eq!(meta.get("title").and_then(|v| v.as_str()), Some("Simple test note"));
        assert!(remaining.contains("## Content"));
    }

    #[test]
    fn test_normalize_inline_tags() {
        let content = "---\nid: 1\ntag: [foo, bar, #baz]\n---\n";
        let (meta, _) = extract_metadata(content);
        assert!(meta.is_some());
        // tag should be normalized to a YAML list
        let tags = meta.unwrap();
        assert!(tags.contains_key("tag"));
    }
}
