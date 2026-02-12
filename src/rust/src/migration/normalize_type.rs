use crate::types::{YamlValue, ZettelData};

/// Normalize type field values.
/// loop -> project, wiki-article -> note, zettel -> note
pub fn migrate(data: &mut ZettelData) {
    let type_val = match data.metadata.get("type") {
        Some(YamlValue::String(s)) if !s.is_empty() => s.clone(),
        _ => return,
    };

    let migrated = match type_val.as_str() {
        "loop" => "project",
        "wiki-article" => "note",
        "zettel" => "note",
        _ => return,
    };

    data.metadata.insert("type".to_string(), YamlValue::String(migrated.to_string()));
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_loop_to_project() {
        let mut data = ZettelData::new();
        data.metadata.insert("type".to_string(), YamlValue::String("loop".to_string()));
        migrate(&mut data);
        assert_eq!(data.metadata.get("type").unwrap().as_str(), Some("project"));
    }

    #[test]
    fn test_wiki_article_to_note() {
        let mut data = ZettelData::new();
        data.metadata.insert("type".to_string(), YamlValue::String("wiki-article".to_string()));
        migrate(&mut data);
        assert_eq!(data.metadata.get("type").unwrap().as_str(), Some("note"));
    }

    #[test]
    fn test_unknown_type_unchanged() {
        let mut data = ZettelData::new();
        data.metadata.insert("type".to_string(), YamlValue::String("custom".to_string()));
        migrate(&mut data);
        assert_eq!(data.metadata.get("type").unwrap().as_str(), Some("custom"));
    }
}
