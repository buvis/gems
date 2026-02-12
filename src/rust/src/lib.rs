use pyo3::prelude::*;

pub mod consistency;
pub mod migration;
pub mod parser;
pub mod pybridge;
pub mod scanner;
pub mod types;

/// Python module: buvis.pybase.zettel._core
#[pymodule]
fn _core(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(pybridge::parse_file, m)?)?;
    m.add_function(wrap_pyfunction!(pybridge::load_all, m)?)?;
    m.add_function(wrap_pyfunction!(pybridge::search, m)?)?;
    Ok(())
}
