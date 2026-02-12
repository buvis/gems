pub mod move_tag_to_tags;
pub mod move_zkn_id;
pub mod normalize_type;
pub mod project;

use crate::types::ZettelData;

/// Run all zettel migrations in order.
/// Mirrors ZettelMigrationService.migrate().
pub fn migrate(data: &mut ZettelData) {
    move_zkn_id::migrate(data);
    move_tag_to_tags::migrate(data);
    normalize_type::migrate(data);
}

/// Run project-specific migrations after base migrations.
/// Mirrors ProjectZettelMigrationService.migrate().
pub fn migrate_project(data: &mut ZettelData) {
    migrate(data);
    project::migrate_loop_log(data);
    project::migrate_parent_reference(data);
}
