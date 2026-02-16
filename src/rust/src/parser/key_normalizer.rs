use std::collections::HashMap;

use regex::Regex;
use std::sync::LazyLock;

use crate::types::YamlValue;

// Matches transitions: lowercase->uppercase, uppercase->lowercase (in sequences),
// non-alpha->alpha boundaries — same behavior as inflection.underscore()
static UNDERSCORE_RE1: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r"([A-Z]+)([A-Z][a-z])").unwrap());
static UNDERSCORE_RE2: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r"([a-z\d])([A-Z])").unwrap());

/// Port of StringCaseTools.as_note_field_name():
/// underscore(text).replace("_", "-").lower()
pub fn as_note_field_name(text: &str) -> String {
    let s = underscore(text);
    s.replace('_', "-").to_lowercase()
}

/// Port of inflection.underscore(): CamelCase -> snake_case
fn underscore(text: &str) -> String {
    let s = text.replace('-', "_").replace(' ', "_");
    let s = UNDERSCORE_RE1.replace_all(&s, "${1}_${2}");
    let s = UNDERSCORE_RE2.replace_all(&s, "${1}_${2}");
    s.to_lowercase()
}

/// Normalize all keys in a HashMap using as_note_field_name.
pub fn normalize_keys(map: HashMap<String, YamlValue>) -> HashMap<String, YamlValue> {
    map.into_iter()
        .map(|(k, v)| (as_note_field_name(&k), v))
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_simple_lowercase() {
        assert_eq!(as_note_field_name("title"), "title");
    }

    #[test]
    fn test_camel_case() {
        assert_eq!(as_note_field_name("SomeValue"), "some-value");
    }

    #[test]
    fn test_space_separated() {
        assert_eq!(as_note_field_name("Note Title"), "note-title");
    }

    #[test]
    fn test_already_kebab() {
        assert_eq!(as_note_field_name("some-value"), "some-value");
    }

    #[test]
    fn test_mixed() {
        assert_eq!(as_note_field_name("zkn-id"), "zkn-id");
    }
}
