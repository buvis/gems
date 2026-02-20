use indexmap::IndexMap;

use regex::Regex;
use std::sync::LazyLock;

use crate::types::YamlValue;

static REFERENCE_RE: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r"(?s)\n---\n(.*)$").unwrap());

static DATAVIEW_KEY_RE: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r"^(\S+)::").unwrap());

/// Extract back matter (reference section) from content.
/// Returns (parsed reference dict, content with back matter removed).
pub fn extract_reference(content: &str) -> (Option<IndexMap<String, YamlValue>>, String) {
    let Some(caps) = REFERENCE_RE.captures(content) else {
        return (None, content.to_string());
    };

    let raw = caps.get(1).unwrap().as_str().trim();
    let preprocessed = quote_unsafe_strings(&fix_dataview_keys(raw));

    let yaml_val: serde_yml::Value = match serde_yml::from_str(&preprocessed) {
        Ok(v) => v,
        Err(_) => return (None, content.to_string()),
    };

    // Back matter is parsed as list of single-key dicts, then merged
    let reference = merge_reference_list(yaml_val);

    // Remove back matter from content
    let without = remove_back_matter(content);

    (Some(reference), without)
}

/// Fix Obsidian dataview keys: `key::` -> `key:`
fn fix_dataview_keys(text: &str) -> String {
    text.lines()
        .map(|line| {
            DATAVIEW_KEY_RE
                .replace(line, |caps: &regex::Captures| {
                    format!("{}:", caps.get(1).unwrap().as_str())
                })
                .to_string()
        })
        .collect::<Vec<_>>()
        .join("\n")
}

/// Quote values containing unsafe YAML chars (`:`, `[`, `]`) if not already quoted.
fn quote_unsafe_strings(text: &str) -> String {
    text.lines()
        .map(|line| {
            if !line.contains(':') {
                return line.to_string();
            }

            let (key, value) = if let Some((k, v)) = line.split_once(": ") {
                (k, v.to_string())
            } else {
                let k = line.split(':').next().unwrap();
                (k, String::new())
            };

            let needs_quoting = (value.contains(':')
                || value.contains('[')
                || value.contains(']'))
                && !value.starts_with('"')
                && !value.ends_with('"');

            if needs_quoting {
                format!("{}: \"{}\"", key, value)
            } else {
                format!("{}: {}", key, value)
            }
        })
        .collect::<Vec<_>>()
        .join("\n")
}

/// Merge YAML list-of-dicts into a single dict.
/// Duplicate keys become lists.
fn merge_reference_list(val: serde_yml::Value) -> IndexMap<String, YamlValue> {
    let mut map: IndexMap<String, YamlValue> = IndexMap::new();

    let items = match val {
        serde_yml::Value::Sequence(seq) => seq,
        _ => return map,
    };

    for item in items {
        if let serde_yml::Value::Mapping(mapping) = item {
            for (k, v) in mapping {
                let key = match k {
                    serde_yml::Value::String(s) => s.trim_end_matches(':').to_string(),
                    _ => continue,
                };
                let value = YamlValue::from(v);

                if let Some(existing) = map.get_mut(&key) {
                    // Convert to list on collision
                    match existing {
                        YamlValue::List(list) => list.push(value),
                        _ => {
                            let prev = std::mem::replace(existing, YamlValue::Null);
                            *existing = YamlValue::List(vec![prev, value]);
                        }
                    }
                } else {
                    map.insert(key, value);
                }
            }
        }
    }

    map
}

/// Remove back matter from content (everything after last standalone `---`).
fn remove_back_matter(content: &str) -> String {
    // Match `^---$` at line start and remove everything after
    let re = Regex::new(r"(?m)(^---$)[\s\S]*").unwrap();
    re.replace(content, "").trim_end().to_string()
}
