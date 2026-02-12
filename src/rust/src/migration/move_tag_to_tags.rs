use crate::types::{YamlValue, ZettelData};

/// Move 'tag' field into 'tags' list.
pub fn migrate(data: &mut ZettelData) {
    let tag = match data.metadata.remove("tag") {
        Some(t) => t,
        None => return,
    };

    // Convert single tag to list
    let tag_items = match tag {
        YamlValue::String(s) => vec![YamlValue::String(s)],
        YamlValue::List(l) => l,
        _ => return,
    };

    // Get or create tags list
    let tags = data
        .metadata
        .entry("tags".to_string())
        .or_insert_with(|| YamlValue::List(Vec::new()));

    if let YamlValue::List(list) = tags {
        list.extend(tag_items);
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_moves_single_tag() {
        let mut data = ZettelData::new();
        data.metadata.insert("tag".to_string(), YamlValue::String("foo".to_string()));

        migrate(&mut data);

        assert!(!data.metadata.contains_key("tag"));
        let tags = data.metadata.get("tags").unwrap().as_list().unwrap();
        assert_eq!(tags.len(), 1);
    }

    #[test]
    fn test_appends_to_existing_tags() {
        let mut data = ZettelData::new();
        data.metadata.insert(
            "tags".to_string(),
            YamlValue::List(vec![YamlValue::String("existing".to_string())]),
        );
        data.metadata.insert("tag".to_string(), YamlValue::String("new".to_string()));

        migrate(&mut data);

        let tags = data.metadata.get("tags").unwrap().as_list().unwrap();
        assert_eq!(tags.len(), 2);
    }

    #[test]
    fn test_no_tag_noop() {
        let mut data = ZettelData::new();
        migrate(&mut data);
        assert!(!data.metadata.contains_key("tag"));
    }
}
