use crate::types::ZettelData;

/// Move 'zkn-id' -> 'id' if 'id' doesn't exist.
pub fn migrate(data: &mut ZettelData) {
    if let Some(zkn_id) = data.metadata.remove("zkn-id") {
        if !data.metadata.contains_key("id") {
            data.metadata.insert("id".to_string(), zkn_id);
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::types::YamlValue;

    #[test]
    fn test_moves_zkn_id_to_id() {
        let mut data = ZettelData::new();
        data.metadata.insert("zkn-id".to_string(), YamlValue::Int(123));

        migrate(&mut data);

        assert!(data.metadata.contains_key("id"));
        assert!(!data.metadata.contains_key("zkn-id"));
    }

    #[test]
    fn test_keeps_existing_id() {
        let mut data = ZettelData::new();
        data.metadata.insert("id".to_string(), YamlValue::Int(456));
        data.metadata.insert("zkn-id".to_string(), YamlValue::Int(123));

        migrate(&mut data);

        assert_eq!(data.metadata.get("id").unwrap().as_int(), Some(456));
        assert!(!data.metadata.contains_key("zkn-id"));
    }
}
