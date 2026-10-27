//! pysequitur_rs: the engine behind pysequitur's Sequencer3, compiled.
//!
//! `Grammar` takes exact `int` (within 64 bits) and exact `str` tokens. Each
//! distinct token gets an id, and the engine works on ids; `rules()` gives the
//! first object seen for each id back. For these two types equal tokens are
//! interchangeable, so the grammar is the one pysequitur's Python engine builds.
//! `feed()` and `stream()` refuse any other token, leaving the grammar as it
//! was, and pysequitur then carries on with its Python engine.

use pyo3::exceptions::PyTypeError;
use pyo3::ffi;
use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList};

mod engine;

use engine::{Engine, IntMap, MAX_ID, NIL, RULE};

/// pysequitur checks this before it uses the module: a build of another
/// version of the algorithm is ignored rather than trusted.
const ENGINE_VERSION: u32 = 1;

/// Ints in 0..SMALL_INTS and characters below U+0100 are looked up in arrays.
const SMALL_INTS: usize = 4096;
const SMALL_CHARS: usize = 256;

/// Inputs at least this long are processed without holding the GIL.
const DETACH_AT: usize = 1 << 16;

#[pyclass(module = "pysequitur_rs")]
struct Grammar {
    engine: Engine,
    /// id -> the first token object seen with that value
    tokens: Vec<Py<PyAny>>,
    small_ints: Vec<u32>,
    ints: IntMap<i64, u32>,
    small_chars: Vec<u32>,
    chars: IntMap<u32, u32>,
    /// str tokens of other lengths than one -> id (a Python int)
    strings: Option<Py<PyDict>>,
}

impl Grammar {
    fn new_id(&mut self, object: Py<PyAny>) -> Option<u32> {
        let id = self.tokens.len();
        if id >= MAX_ID as usize {
            return None;
        }
        self.tokens.push(object);
        Some(id as u32)
    }

    fn char_id(
        &mut self,
        py: Python<'_>,
        cp: u32,
        object: *mut ffi::PyObject,
    ) -> PyResult<Option<u32>> {
        if (cp as usize) < SMALL_CHARS {
            let id = self.small_chars[cp as usize];
            if id != NIL {
                return Ok(Some(id));
            }
        } else if let Some(&id) = self.chars.get(&cp) {
            return Ok(Some(id));
        }
        let object = if object.is_null() {
            // a character of a str input: make the one-character string that
            // iterating over the input would give
            unsafe {
                let o = ffi::PyUnicode_FromOrdinal(cp as i32);
                if o.is_null() {
                    return Err(PyErr::fetch(py));
                }
                Bound::from_owned_ptr(py, o).unbind()
            }
        } else {
            unsafe { Bound::from_borrowed_ptr(py, object).unbind() }
        };
        let id = match self.new_id(object) {
            Some(id) => id,
            None => return Ok(None),
        };
        if (cp as usize) < SMALL_CHARS {
            self.small_chars[cp as usize] = id;
        } else {
            self.chars.insert(cp, id);
        }
        Ok(Some(id))
    }

    /// The id of a token, or None for a token of a type the engine does not take.
    ///
    /// Safety: `object` is a valid object, and the GIL is held. Nothing here
    /// runs Python code: exact ints and strs hash and compare in C.
    unsafe fn intern(
        &mut self,
        py: Python<'_>,
        object: *mut ffi::PyObject,
    ) -> PyResult<Option<u32>> {
        if ffi::PyLong_CheckExact(object) != 0 {
            let mut overflow = 0;
            let v = ffi::PyLong_AsLongLongAndOverflow(object, &mut overflow);
            if overflow != 0 {
                return Ok(None);
            }
            if v == -1 && !ffi::PyErr_Occurred().is_null() {
                return Err(PyErr::fetch(py));
            }
            if (v as u64) < SMALL_INTS as u64 {
                let id = self.small_ints[v as usize];
                if id != NIL {
                    return Ok(Some(id));
                }
                let id = self.new_id(Bound::from_borrowed_ptr(py, object).unbind());
                if let Some(id) = id {
                    self.small_ints[v as usize] = id;
                }
                return Ok(id);
            }
            if let Some(&id) = self.ints.get(&v) {
                return Ok(Some(id));
            }
            let id = self.new_id(Bound::from_borrowed_ptr(py, object).unbind());
            if let Some(id) = id {
                self.ints.insert(v, id);
            }
            return Ok(id);
        }
        if ffi::PyUnicode_CheckExact(object) != 0 {
            let n = ffi::PyUnicode_GetLength(object);
            if n == 1 {
                let cp = ffi::PyUnicode_ReadChar(object, 0);
                if cp == u32::MAX as ffi::Py_UCS4 {
                    return Err(PyErr::fetch(py));
                }
                return self.char_id(py, cp as u32, object);
            }
            let strings = self
                .strings
                .get_or_insert_with(|| PyDict::new(py).unbind())
                .bind(py)
                .clone();
            let token = Bound::from_borrowed_ptr(py, object);
            if let Some(id) = strings.get_item(&token)? {
                return Ok(Some(id.extract::<u32>()?));
            }
            let id = self.new_id(token.clone().unbind());
            if let Some(id) = id {
                strings.set_item(&token, id)?;
            }
            return Ok(id);
        }
        Ok(None)
    }

    /// Ids of the tokens of an exact list, tuple or str; None if one of them
    /// is of a type the engine does not take.
    fn ids(&mut self, tokens: &Bound<'_, PyAny>) -> PyResult<Option<Vec<u32>>> {
        let py = tokens.py();
        let p = tokens.as_ptr();
        unsafe {
            if ffi::PyList_CheckExact(p) != 0 {
                // Interning runs no Python code, but a new dict could start a
                // garbage collection, and a finalizer could change the list:
                // read its length each time and hold on to each item.
                let mut ids = Vec::with_capacity(ffi::PyList_GET_SIZE(p) as usize);
                let mut i = 0;
                while i < ffi::PyList_GET_SIZE(p) {
                    let item = Bound::from_borrowed_ptr(py, ffi::PyList_GET_ITEM(p, i));
                    match self.intern(py, item.as_ptr())? {
                        Some(id) => ids.push(id),
                        None => return Ok(None),
                    }
                    i += 1;
                }
                return Ok(Some(ids));
            }
            if ffi::PyTuple_CheckExact(p) != 0 {
                let n = ffi::PyTuple_GET_SIZE(p);
                let mut ids = Vec::with_capacity(n as usize);
                for i in 0..n {
                    match self.intern(py, ffi::PyTuple_GET_ITEM(p, i))? {
                        Some(id) => ids.push(id),
                        None => return Ok(None),
                    }
                }
                return Ok(Some(ids));
            }
            if ffi::PyUnicode_CheckExact(p) != 0 {
                let n = ffi::PyUnicode_GetLength(p);
                if n == 0 {
                    return Ok(Some(Vec::new()));
                }
                let buffer = ffi::PyUnicode_AsUCS4Copy(p);
                if buffer.is_null() {
                    return Err(PyErr::fetch(py));
                }
                let chars = std::slice::from_raw_parts(buffer as *const u32, n as usize);
                let mut ids = Vec::with_capacity(n as usize);
                let mut result = Ok(Some(()));
                for &cp in chars {
                    match self.char_id(py, cp, std::ptr::null_mut()) {
                        Ok(Some(id)) => ids.push(id),
                        Ok(None) => {
                            result = Ok(None);
                            break;
                        }
                        Err(e) => {
                            result = Err(e);
                            break;
                        }
                    }
                }
                ffi::PyMem_Free(buffer as *mut std::ffi::c_void);
                return result.map(|r| r.map(|_| ids));
            }
        }
        Err(PyTypeError::new_err(
            "feed() takes a list, a tuple or a str",
        ))
    }

    fn token_list<'py>(&self, py: Python<'py>, ids: &[u32]) -> PyResult<Bound<'py, PyList>> {
        unsafe {
            let list = ffi::PyList_New(ids.len() as ffi::Py_ssize_t);
            if list.is_null() {
                return Err(PyErr::fetch(py));
            }
            for (j, &id) in ids.iter().enumerate() {
                let o = self.tokens[id as usize].as_ptr();
                ffi::Py_INCREF(o);
                ffi::PyList_SET_ITEM(list, j as ffi::Py_ssize_t, o);
            }
            Ok(Bound::from_owned_ptr(py, list).cast_into_unchecked())
        }
    }
}

#[pymethods]
impl Grammar {
    #[new]
    fn py_new() -> Self {
        Grammar {
            engine: Engine::new(),
            tokens: Vec::new(),
            small_ints: vec![NIL; SMALL_INTS],
            ints: IntMap::default(),
            small_chars: vec![NIL; SMALL_CHARS],
            chars: IntMap::default(),
            strings: None,
        }
    }

    /// Number of tokens read so far.
    fn __len__(&self) -> usize {
        self.engine.len() as usize
    }

    /// Append one token. False, and nothing appended, if the engine does not
    /// take tokens of its type.
    fn stream(&mut self, token: &Bound<'_, PyAny>) -> PyResult<bool> {
        match unsafe { self.intern(token.py(), token.as_ptr())? } {
            Some(id) => {
                self.engine.stream(id);
                Ok(true)
            }
            None => Ok(false),
        }
    }

    /// Append the tokens of an exact list, tuple or str. False, and nothing
    /// appended, if one of them is of a type the engine does not take.
    fn feed(&mut self, tokens: &Bound<'_, PyAny>) -> PyResult<bool> {
        let ids = match self.ids(tokens)? {
            Some(ids) => ids,
            None => return Ok(false),
        };
        if ids.len() >= DETACH_AT {
            let engine = &mut self.engine;
            tokens.py().detach(|| engine.feed(&ids));
        } else {
            self.engine.feed(&ids);
        }
        Ok(true)
    }

    /// The rules as lists, the main rule first and the others in order of
    /// first use, rule references as `rule_index(i)`: `core.Grammar.rules()`.
    fn rules<'py>(&self, rule_index: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyList>> {
        let py = rule_index.py();
        let mut items = Vec::new();
        let mut ends = Vec::new();
        self.engine.rules(&mut items, &mut ends);
        let cls = rule_index.as_ptr();
        unsafe {
            let outer = ffi::PyList_New(ends.len() as ffi::Py_ssize_t);
            if outer.is_null() {
                return Err(PyErr::fetch(py));
            }
            let outer = Bound::from_owned_ptr(py, outer);
            let mut start = 0;
            for (k, &end) in ends.iter().enumerate() {
                let inner = ffi::PyList_New((end - start) as ffi::Py_ssize_t);
                if inner.is_null() {
                    return Err(PyErr::fetch(py));
                }
                // owned by outer from here on, so freed with it on an error
                ffi::PyList_SET_ITEM(outer.as_ptr(), k as ffi::Py_ssize_t, inner);
                for (j, &item) in items[start..end].iter().enumerate() {
                    let o = if item & RULE == 0 {
                        let o = self.tokens[item as usize].as_ptr();
                        ffi::Py_INCREF(o);
                        o
                    } else {
                        let n = ffi::PyLong_FromSsize_t((item & !RULE) as ffi::Py_ssize_t);
                        if n.is_null() {
                            return Err(PyErr::fetch(py));
                        }
                        let o = ffi::PyObject_CallOneArg(cls, n);
                        ffi::Py_DECREF(n);
                        if o.is_null() {
                            return Err(PyErr::fetch(py));
                        }
                        o
                    };
                    ffi::PyList_SET_ITEM(inner, j as ffi::Py_ssize_t, o);
                }
                start = end;
            }
            Ok(outer.cast_into_unchecked())
        }
    }

    /// (number of rules, total number of symbols in them) of `rules()`,
    /// without building it.
    fn size(&self) -> (usize, usize) {
        self.engine.size()
    }

    /// The input read so far, the main rule expanded.
    fn expand<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyList>> {
        let ids = self.engine.expand();
        self.token_list(py, &ids)
    }
}

#[pymodule]
fn pysequitur_rs(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<Grammar>()?;
    m.add("ENGINE_VERSION", ENGINE_VERSION)?;
    m.add("__version__", env!("CARGO_PKG_VERSION"))?;
    Ok(())
}
