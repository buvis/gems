use regex::Regex;
use std::sync::LazyLock;

static HEADING_RE: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r"(#{1,6} .+?)\n").unwrap());

/// Split content into (heading, body) sections.
/// Mirrors Python's split_content_into_sections().
pub fn split_into_sections(content: &str) -> Vec<(String, String)> {
    let parts: Vec<&str> = HEADING_RE.split(content).collect();
    let headings: Vec<&str> = HEADING_RE
        .captures_iter(content)
        .map(|c| c.get(1).unwrap().as_str())
        .collect();

    if headings.is_empty() {
        return vec![("".to_string(), content.to_string())];
    }

    // parts[0] is before first heading (skip), then alternating content
    headings
        .iter()
        .enumerate()
        .map(|(i, heading)| {
            let body = parts.get(i + 1).unwrap_or(&"");
            (heading.to_string(), body.to_string())
        })
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_split_no_headings() {
        let result = split_into_sections("just some text\n");
        assert_eq!(result, vec![("".to_string(), "just some text\n".to_string())]);
    }

    #[test]
    fn test_split_single_heading() {
        let result = split_into_sections("# Title\nsome body\n");
        assert_eq!(result.len(), 1);
        assert_eq!(result[0].0, "# Title");
        assert_eq!(result[0].1, "some body\n");
    }

    #[test]
    fn test_split_multiple_headings() {
        let input = "# Title\nbody1\n## Sub\nbody2\n";
        let result = split_into_sections(input);
        assert_eq!(result.len(), 2);
        assert_eq!(result[0].0, "# Title");
        assert_eq!(result[1].0, "## Sub");
    }
}
