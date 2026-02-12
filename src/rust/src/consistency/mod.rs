pub mod defaults;
pub mod fixers;

use crate::types::ZettelData;

/// Run all zettel consistency checks.
/// Mirrors ZettelConsistencyService.ensure_consistency().
pub fn ensure_consistency(data: &mut ZettelData) {
    defaults::set_missing_defaults(data);
    fixers::remove_duplicate_tags(data);
    fixers::sort_tags(data);
    fixers::fix_title_format(data);
    fixers::align_h1_to_title(data);
}

/// Run project-specific consistency after base consistency.
/// Mirrors ProjectZettelConsistencyService.ensure_consistency().
pub fn ensure_project_consistency(data: &mut ZettelData) {
    fixers::fix_lists_bullets(data);
    fixers::normalize_sections_order(data);
    fixers::set_default_completed(data);
}
