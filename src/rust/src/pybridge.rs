use std::path::Path;

use chrono::{Datelike, Timelike};
use pyo3::prelude::*;
use pyo3::types::{PyDateTime, PyDict, PyList, PyTuple, PyTzInfo};

use crate::consistency;
use crate::migration;
use crate::parser;
use crate::scanner;
use crate::scanner::MetaFilterValue;
use crate::types::{YamlValue, ZettelData};

/// Convert YamlValue to a Python object.
fn yaml_value_to_py(py: Python<'_>, val: &YamlValue) -> PyResult<Py<PyAny>> {
    match val {
        YamlValue::Null => Ok(py.None()),
        YamlValue::Bool(b) => Ok(b.into_pyobject(py)?.to_owned().into_any().unbind()),
        YamlValue::Int(i) => Ok(i.into_pyobject(py)?.into_any().unbind()),
        YamlValue::Float(f) => Ok(f.into_pyobject(py)?.into_any().unbind()),
        YamlValue::String(s) => Ok(s.into_pyobject(py)?.into_any().unbind()),
        YamlValue::List(items) => {
            let py_items: Vec<Py<PyAny>> = items
                .iter()
                .map(|item| yaml_value_to_py(py, item))
                .collect::<PyResult<_>>()?;
            Ok(PyList::new(py, &py_items)?.into_any().unbind())
        }
        YamlValue::DateTime(dt) => {
            let utc_dt = dt.with_timezone(&chrono::Utc);
            let datetime_mod = py.import("datetime")?;
            let tz_class = datetime_mod.getattr("timezone")?;
            let utc_tz: Bound<'_, PyTzInfo> = tz_class.getattr("utc")?.cast_into()?;
            let py_dt = PyDateTime::new(
                py,
                utc_dt.year(),
                utc_dt.month() as u8,
                utc_dt.day() as u8,
                utc_dt.hour() as u8,
                utc_dt.minute() as u8,
                utc_dt.second() as u8,
                0,
                Some(&utc_tz),
            )?;
            Ok(py_dt.into_any().unbind())
        }
    }
}

/// Convert HashMap<String, YamlValue> to Python dict.
fn map_to_pydict(
    py: Python<'_>,
    map: &std::collections::HashMap<String, YamlValue>,
) -> PyResult<Py<PyDict>> {
    let dict = PyDict::new(py);
    for (key, val) in map {
        dict.set_item(key, yaml_value_to_py(py, val)?)?;
    }
    Ok(dict.unbind())
}

/// Convert sections to Python list of tuples.
fn sections_to_pylist(py: Python<'_>, sections: &[(String, String)]) -> PyResult<Py<PyList>> {
    let items: Vec<Py<PyTuple>> = sections
        .iter()
        .map(|(heading, content)| {
            Ok(PyTuple::new(py, &[heading.as_str(), content.as_str()])?.unbind())
        })
        .collect::<PyResult<_>>()?;
    Ok(PyList::new(py, &items)?.unbind())
}

/// Convert ZettelData to a Python dict with metadata, reference, sections, file_path.
fn zettel_data_to_pydict(py: Python<'_>, data: &ZettelData) -> PyResult<Py<PyAny>> {
    let dict = PyDict::new(py);
    dict.set_item("metadata", map_to_pydict(py, &data.metadata)?)?;
    dict.set_item("reference", map_to_pydict(py, &data.reference)?)?;
    dict.set_item("sections", sections_to_pylist(py, &data.sections)?)?;
    dict.set_item(
        "file_path",
        data.file_path
            .as_ref()
            .map(|s| s.as_str())
            .unwrap_or(""),
    )?;
    Ok(dict.into_any().unbind())
}

/// Parse a single file with full fallback (filesystem date).
/// Returns a dict with metadata, reference, sections, file_path.
#[pyfunction]
pub fn parse_file(py: Python<'_>, path: &str) -> PyResult<Py<PyAny>> {
    let file_path = Path::new(path);
    let mut data = parser::parse_file_with_fallback(file_path)
        .map_err(|e| pyo3::exceptions::PyIOError::new_err(e))?;

    apply_pipeline(&mut data);
    zettel_data_to_pydict(py, &data)
}

/// Bulk load all markdown files from a directory.
/// Returns a list of dicts.
#[pyfunction]
#[pyo3(signature = (directory, extensions=None))]
pub fn load_all(py: Python<'_>, directory: &str, extensions: Option<Vec<String>>) -> PyResult<Py<PyAny>> {
    let exts = extensions.unwrap_or_else(|| vec!["md".to_string()]);
    let results = scanner::load_all(directory, &exts)
        .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e))?;

    let py_list: Vec<Py<PyAny>> = results
        .iter()
        .map(|data| zettel_data_to_pydict(py, data))
        .collect::<PyResult<_>>()?;

    Ok(PyList::new(py, &py_list)?.into_any().unbind())
}

/// Bulk load with metadata eq filtering. Returns only matching dicts.
#[pyfunction]
#[pyo3(signature = (directory, extensions=None, metadata_eq=None, cache_path=None))]
pub fn load_filtered(
    py: Python<'_>,
    directory: &str,
    extensions: Option<Vec<String>>,
    metadata_eq: Option<&Bound<'_, PyDict>>,
    cache_path: Option<&str>,
) -> PyResult<Py<PyAny>> {
    let exts = extensions.unwrap_or_else(|| vec!["md".to_string()]);

    let conditions = match metadata_eq {
        Some(dict) => pydict_to_conditions(py, dict)?,
        None => vec![],
    };

    if conditions.is_empty() {
        // No filter — fall back to load_all
        return load_all(py, directory, Some(exts));
    }

    let results = if let Some(cp) = cache_path {
        scanner::load_cached(directory, &exts, &conditions, cp)
    } else {
        scanner::load_filtered(directory, &exts, &conditions)
    }
    .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e))?;

    let py_list: Vec<Py<PyAny>> = results
        .iter()
        .map(|data| zettel_data_to_pydict(py, data))
        .collect::<PyResult<_>>()?;

    Ok(PyList::new(py, &py_list)?.into_any().unbind())
}

/// Convert a Python dict of {str: value} to Rust filter conditions.
fn pydict_to_conditions(_py: Python<'_>, dict: &Bound<'_, PyDict>) -> PyResult<Vec<(String, MetaFilterValue)>> {
    let mut conditions = Vec::new();
    for (key, value) in dict.iter() {
        let key_str: String = key.extract()?;
        let filter_val = if let Ok(b) = value.extract::<bool>() {
            MetaFilterValue::Bool(b)
        } else if let Ok(i) = value.extract::<i64>() {
            MetaFilterValue::Int(i)
        } else if let Ok(s) = value.extract::<String>() {
            MetaFilterValue::Str(s)
        } else {
            return Err(pyo3::exceptions::PyTypeError::new_err(
                format!("Unsupported filter value type for key '{}'", key_str),
            ));
        };
        conditions.push((key_str, filter_val));
    }
    Ok(conditions)
}

/// Full-text search across a directory. Returns matching zettels.
#[pyfunction]
#[pyo3(signature = (directory, query, extensions=None))]
pub fn search(
    py: Python<'_>,
    directory: &str,
    query: &str,
    extensions: Option<Vec<String>>,
) -> PyResult<Py<PyAny>> {
    let exts = extensions.unwrap_or_else(|| vec!["md".to_string()]);
    let results = scanner::search(directory, query, &exts)
        .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e))?;

    let py_list: Vec<Py<PyAny>> = results
        .iter()
        .map(|data| zettel_data_to_pydict(py, data))
        .collect::<PyResult<_>>()?;

    Ok(PyList::new(py, &py_list)?.into_any().unbind())
}

/// Background cache refresh: walk directory, update cache, write stale marker if changed.
/// Returns summary string (empty if no changes).
#[pyfunction]
#[pyo3(signature = (directory, cache_path, extensions=None))]
pub fn refresh_cache(
    directory: &str,
    cache_path: &str,
    extensions: Option<Vec<String>>,
) -> PyResult<String> {
    let exts = extensions.unwrap_or_else(|| vec!["md".to_string()]);
    scanner::refresh_cache(directory, &exts, cache_path)
        .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e))
}

/// Apply the full zettel processing pipeline.
fn apply_pipeline(data: &mut ZettelData) {
    let is_project = data
        .metadata
        .get("type")
        .and_then(|v| v.as_str())
        .map(|t| t == "project" || t == "loop")
        .unwrap_or(false);

    consistency::ensure_consistency(data);
    if is_project {
        consistency::ensure_project_consistency(data);
    }

    if is_project {
        migration::migrate_project(data);
    } else {
        migration::migrate(data);
    }

    consistency::ensure_consistency(data);
    if is_project {
        consistency::ensure_project_consistency(data);
    }
}
