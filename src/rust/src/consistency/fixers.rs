use std::collections::HashSet;

use crate::types::{YamlValue, ZettelData};

/// Remove duplicate tags (convert to set, back to list).
pub fn remove_duplicate_tags(data: &mut ZettelData) {
    if let Some(YamlValue::List(tags)) = data.metadata.get("tags") {
        let mut seen = HashSet::new();
        let deduped: Vec<YamlValue> = tags
            .iter()
            .filter(|t| {
                if let YamlValue::String(s) = t {
                    seen.insert(s.clone())
                } else {
                    true
                }
            })
            .cloned()
            .collect();
        data.metadata
            .insert("tags".to_string(), YamlValue::List(deduped));
    }
}

/// Sort tags alphabetically.
pub fn sort_tags(data: &mut ZettelData) {
    if let Some(YamlValue::List(tags)) = data.metadata.get_mut("tags") {
        tags.sort_by(|a, b| {
            let sa = match a {
                YamlValue::String(s) => s.as_str(),
                _ => "",
            };
            let sb = match b {
                YamlValue::String(s) => s.as_str(),
                _ => "",
            };
            sa.cmp(sb)
        });
    }
}

/// Fix title format: trim whitespace and capitalize first letter.
/// The Python version calls replace_abbreviations(level=0) with empty list,
/// which is a no-op, so we skip it.
pub fn fix_title_format(data: &mut ZettelData) {
    if let Some(YamlValue::String(title)) = data.metadata.get("title") {
        let trimmed = title.trim();
        if trimmed.is_empty() {
            return;
        }
        let mut chars = trimmed.chars();
        let capitalized = match chars.next() {
            Some(c) => {
                let upper: String = c.to_uppercase().collect();
                upper + chars.as_str()
            }
            None => return,
        };
        data.metadata
            .insert("title".to_string(), YamlValue::String(capitalized));
    }
}

/// Align first section heading to match metadata title.
pub fn align_h1_to_title(data: &mut ZettelData) {
    let title = match data.metadata.get("title") {
        Some(YamlValue::String(t)) => t.clone(),
        _ => return,
    };

    let title_heading = format!("# {}", title);

    if let Some((heading, content)) = data.sections.first() {
        if !heading.starts_with("# ") || *heading != title_heading {
            let content = content.clone();
            data.sections[0] = (title_heading, content);
        }
    } else {
        data.sections.push((title_heading, String::new()));
    }
}

/// Convert `* ` list bullets to `- ` in all sections. (Project-specific)
pub fn fix_lists_bullets(data: &mut ZettelData) {
    data.sections = data
        .sections
        .iter()
        .map(|(heading, content)| {
            let fixed: String = content
                .lines()
                .map(|line| {
                    if line.starts_with("* ") {
                        format!("- {}", line[2..].trim())
                    } else {
                        line.trim().to_string()
                    }
                })
                .collect::<Vec<_>>()
                .join("\n");
            (heading.clone(), fixed)
        })
        .collect();
}

/// Reorder sections: title, Description, Log, Actions buffer, then rest. (Project-specific)
pub fn normalize_sections_order(data: &mut ZettelData) {
    let mut title_sec: Option<(String, String)> = None;
    let mut desc_sec: Option<(String, String)> = None;
    let mut log_sec: Option<(String, String)> = None;
    let mut actions_sec: Option<(String, String)> = None;
    let mut others: Vec<(String, String)> = Vec::new();

    for section in &data.sections {
        let (heading, _) = section;
        if heading.starts_with("# ") && title_sec.is_none() {
            title_sec = Some(section.clone());
        } else if heading == "## Description" {
            desc_sec = Some(section.clone());
        } else if heading == "## Log" {
            log_sec = Some(section.clone());
        } else if heading == "## Actions buffer" {
            actions_sec = Some(section.clone());
        } else {
            others.push(section.clone());
        }
    }

    let mut reordered = Vec::new();
    if let Some(s) = title_sec {
        reordered.push(s);
    }
    if let Some(s) = desc_sec {
        reordered.push(s);
    }
    if let Some(s) = log_sec {
        reordered.push(s);
    }
    if let Some(s) = actions_sec {
        reordered.push(s);
    }
    reordered.extend(others);

    data.sections = reordered;
}

/// Set default completed status. (Project-specific)
/// If gtd-list == "completed", set completed = true and remove gtd-list.
pub fn set_default_completed(data: &mut ZettelData) {
    if let Some(YamlValue::Bool(true)) = data.metadata.get("completed") {
        return; // already set
    }

    let is_gtd_completed = match data.metadata.get("gtd-list") {
        Some(YamlValue::String(s)) => s == "completed",
        _ => false,
    };

    if is_gtd_completed {
        data.metadata
            .insert("completed".to_string(), YamlValue::Bool(true));
        data.metadata.shift_remove("gtd-list");
    } else if !data.metadata.contains_key("completed") {
        data.metadata
            .insert("completed".to_string(), YamlValue::Bool(false));
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_remove_duplicate_tags() {
        let mut data = ZettelData::new();
        data.metadata.insert(
            "tags".to_string(),
            YamlValue::List(vec![
                YamlValue::String("a".to_string()),
                YamlValue::String("b".to_string()),
                YamlValue::String("a".to_string()),
            ]),
        );
        remove_duplicate_tags(&mut data);
        let tags = data.metadata.get("tags").unwrap().as_list().unwrap();
        assert_eq!(tags.len(), 2);
    }

    #[test]
    fn test_sort_tags() {
        let mut data = ZettelData::new();
        data.metadata.insert(
            "tags".to_string(),
            YamlValue::List(vec![
                YamlValue::String("c".to_string()),
                YamlValue::String("a".to_string()),
                YamlValue::String("b".to_string()),
            ]),
        );
        sort_tags(&mut data);
        let tags = data.metadata.get("tags").unwrap().as_list().unwrap();
        assert_eq!(tags[0].as_str(), Some("a"));
        assert_eq!(tags[1].as_str(), Some("b"));
        assert_eq!(tags[2].as_str(), Some("c"));
    }

    #[test]
    fn test_fix_title_format() {
        let mut data = ZettelData::new();
        data.metadata.insert(
            "title".to_string(),
            YamlValue::String("  some title  ".to_string()),
        );
        fix_title_format(&mut data);
        assert_eq!(
            data.metadata.get("title").unwrap().as_str(),
            Some("Some title")
        );
    }

    #[test]
    fn test_align_h1_to_title() {
        let mut data = ZettelData::new();
        data.metadata.insert(
            "title".to_string(),
            YamlValue::String("My title".to_string()),
        );
        data.sections.push(("# Old title".to_string(), "body".to_string()));
        align_h1_to_title(&mut data);
        assert_eq!(data.sections[0].0, "# My title");
    }

    #[test]
    fn test_fix_lists_bullets() {
        let mut data = ZettelData::new();
        data.sections.push(("# T".to_string(), "* item1\n* item2\n- item3".to_string()));
        fix_lists_bullets(&mut data);
        assert!(data.sections[0].1.contains("- item1"));
        assert!(data.sections[0].1.contains("- item2"));
        assert!(data.sections[0].1.contains("- item3"));
    }
}
