use chrono::{DateTime, Local, NaiveDateTime};
use regex::Regex;
use std::sync::LazyLock;

use crate::types::{YamlValue, ZettelData};

static LOG_ENTRY_RE: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r"^(\d{2}\.\d{2}\.\d{4} \d{2}:\d{2}) - (.*?)(?:\s*=>\s*(.*))?$").unwrap());

static DATE_PATTERN_RE: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r"\b(\d{4}-\d{2}-\d{2})\b").unwrap());

static WIKI_LINK_RE: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r"\[\[(.*?)\]\]").unwrap());

struct NextAction {
    gtd_list: String,
    priority: String,
    dates: String,
}

struct DateParseResult {
    date: Option<NaiveDateTime>,
    before: String,
}

/// Migrate loop log entries from first section content into a structured ## Log section.
pub fn migrate_loop_log(data: &mut ZettelData) {
    if data.sections.is_empty() {
        return;
    }

    let (header, content) = &data.sections[0];
    let header = header.clone();
    let (log_entries, remaining) = extract_log_entries(content);
    let next_action = get_next_action_properties(data);
    let formatted_log = format_log_entries(&log_entries, &next_action);

    data.sections[0] = (header, remaining.join("\n"));
    if !formatted_log.is_empty() {
        data.sections.push(("## Log".to_string(), formatted_log));
    }
}

/// Migrate parent reference to wiki-link format.
pub fn migrate_parent_reference(data: &mut ZettelData) {
    let parent = match data.reference.get("parent") {
        Some(YamlValue::String(s)) => s.clone(),
        _ => return,
    };

    let link = match WIKI_LINK_RE.captures(&parent) {
        Some(caps) => caps.get(1).unwrap().as_str().to_string(),
        None => return,
    };

    let id_str = data
        .metadata
        .get("id")
        .map(|v| match v {
            YamlValue::Int(i) => i.to_string(),
            YamlValue::String(s) => s.clone(),
            _ => String::new(),
        })
        .unwrap_or_default();

    let title = data
        .metadata
        .get("title")
        .and_then(|v| v.as_str())
        .unwrap_or("")
        .to_string();

    let new_parent = if link == id_str {
        format!("[[zettelkasten/{}|{}]]", id_str, title)
    } else {
        format!("[[{}]]", link)
    };

    data.reference.insert("parent".to_string(), YamlValue::String(new_parent));
}

struct LogEntry {
    date: DateTime<Local>,
    before: String,
    after: String,
}

fn extract_log_entries(content: &str) -> (Vec<LogEntry>, Vec<String>) {
    let mut entries = Vec::new();
    let mut unmatched = Vec::new();

    for line in content.lines() {
        let trimmed = line.trim();
        if let Some(caps) = LOG_ENTRY_RE.captures(trimmed) {
            let date_str = caps.get(1).unwrap().as_str();
            let before = caps.get(2).unwrap().as_str().trim().to_string();
            let after = caps
                .get(3)
                .map(|m| m.as_str().trim().to_string())
                .unwrap_or_default();

            if let Ok(naive) = NaiveDateTime::parse_from_str(date_str, "%d.%m.%Y %H:%M") {
                let local = naive.and_local_timezone(Local).unwrap();
                entries.push(LogEntry {
                    date: local,
                    before,
                    after,
                });
            }
        } else if !trimmed.is_empty() {
            unmatched.push(trimmed.to_string());
        }
    }

    (entries, unmatched)
}

fn get_next_action_properties(data: &mut ZettelData) -> NextAction {
    let priority_map: &[(&str, &str)] = &[
        ("could", "\u{23EC}"),  // ⏬
        ("would", "\u{1F53D}"), // 🔽
        ("should", "\u{1F53C}"), // 🔼
        ("must", "\u{23EB}"),   // ⏫
    ];
    let before_map: &[(&str, &str)] = &[
        ("start", "start"),
        ("end", "before"),
        ("complete", "before"),
    ];

    // Find first metadata key with a dash (importance-action pattern)
    let matching_key = data
        .metadata
        .iter()
        .find(|(k, _)| k.contains('-'))
        .map(|(k, v)| {
            let val_str = match v {
                YamlValue::String(s) => s.clone(),
                YamlValue::Int(i) => i.to_string(),
                _ => String::new(),
            };
            (k.clone(), val_str)
        });

    let (key, target_date) = match matching_key {
        Some(kv) => kv,
        None => {
            return NextAction {
                gtd_list: "#gtd/inbox".to_string(),
                priority: "\u{1F53C}".to_string(), // 🔼
                dates: String::new(),
            }
        }
    };

    let parts: Vec<&str> = key.splitn(2, '-').collect();
    if parts.len() != 2 {
        return NextAction {
            gtd_list: "#gtd/inbox".to_string(),
            priority: "\u{1F53C}".to_string(),
            dates: String::new(),
        };
    }

    let importance = parts[0];
    let action = parts[1];

    let priority = match priority_map.iter().find(|(k, _)| *k == importance) {
        Some((_, p)) => p.to_string(),
        None => {
            return NextAction {
                gtd_list: String::new(),
                priority: String::new(),
                dates: String::new(),
            }
        }
    };

    let gtd_list = if action == "wait" {
        "#gtd/wait".to_string()
    } else {
        let list_name = determine_gtd_list(&target_date);
        format!("#gtd/act/{}", list_name)
    };

    let mut milestone = parse_date_string(&target_date);
    if let Some((_, mapped)) = before_map.iter().find(|(k, _)| *k == action) {
        milestone.before = mapped.to_string();
    }

    let dates = create_dates_section(&milestone);

    // Remove the processed key
    data.metadata.remove(&key);

    NextAction {
        gtd_list,
        priority,
        dates,
    }
}

fn determine_gtd_list(target_date: &str) -> String {
    let result = parse_date_string(target_date);
    match result.before.as_str() {
        "now" | "next" | "someday" | "later" => result.before,
        _ => "now".to_string(),
    }
}

fn parse_date_string(input: &str) -> DateParseResult {
    let input = input.trim();
    if let Some(caps) = DATE_PATTERN_RE.captures(input) {
        let date_str = caps.get(1).unwrap().as_str();
        if let Ok(date) = NaiveDateTime::parse_from_str(
            &format!("{} 00:00:00", date_str),
            "%Y-%m-%d %H:%M:%S",
        ) {
            let before = input[..caps.get(1).unwrap().start()].trim().to_string();
            return DateParseResult {
                date: Some(date),
                before,
            };
        }
    }

    DateParseResult {
        date: None,
        before: input.to_string(),
    }
}

fn create_dates_section(milestone: &DateParseResult) -> String {
    let date = match &milestone.date {
        Some(d) => d,
        None => return String::new(),
    };

    let formatted = date.format("%Y-%m-%d").to_string();

    match milestone.before.as_str() {
        "" | "before" => format!("\u{1F4C5} {}", formatted),     // 📅
        "start" | "after" => format!("\u{1F6EB} {}", formatted), // 🛫
        "on" => format!("\u{23F3} {}", formatted),               // ⏳
        _ => String::new(),
    }
}

fn format_log_entries(entries: &[LogEntry], next_action: &NextAction) -> String {
    let mut output = String::new();
    let mut task_status = " ";
    let mut gtd_list = next_action.gtd_list.clone();
    let priority = &next_action.priority;
    let dates = &next_action.dates;

    for entry in entries {
        let date_str = entry.date.format("%Y-%m-%d %H:%M").to_string();

        if entry.after.is_empty() {
            output.push_str(&format!("- [i] {} - {}\n", date_str, entry.before));
        } else {
            let task_props = if !gtd_list.is_empty() {
                let gl = format!(" {} ", gtd_list);
                if !dates.is_empty() {
                    format!(" |{}{} {}", gl, priority, dates)
                } else {
                    format!(" |{}{}", gl, priority)
                }
            } else if !dates.is_empty() {
                format!(" | {} {}", priority, dates)
            } else {
                format!(" | {}", priority)
            };

            output.push_str(&format!(
                "- [{}] {} - {} => {}{}\n",
                task_status, date_str, entry.before, entry.after, task_props
            ));
            task_status = "x";
            gtd_list = String::new();
        }
    }

    output
}
