// Rust Synthetic Parser & Resolution Fixture
// Covers 6 required constructs for LFCG extraction and resolution:
// 1. Module paths
// 2. use aliases
// 3. Associated functions
// 4. Trait methods
// 5. Macro-generated code
// 6. Ambiguous calls

pub mod internal_module {
    pub fn module_target_func() -> &'static str {
        "module_target"
    }

    pub struct Worker;

    impl Worker {
        pub fn associated_create() -> Self {
            Worker
        }

        pub fn member_action(&self) -> bool {
            true
        }
    }
}

// 2. use aliases
use std::collections::HashMap as MapAlias;
use crate::internal_module::module_target_func as target_alias;

// 4. Trait definitions and implementations
pub trait DataHandler {
    fn handle_data(&self, input: &str) -> String;
}

pub struct FirstHandler;
pub struct SecondHandler;

impl DataHandler for FirstHandler {
    fn handle_data(&self, input: &str) -> String {
        format!("first:{}", input)
    }
}

// 6. Ambiguous calls: another struct with same method name
impl DataHandler for SecondHandler {
    fn handle_data(&self, input: &str) -> String {
        format!("second:{}", input)
    }
}

pub struct UnrelatedService;
impl UnrelatedService {
    pub fn handle_data(&self, input: &str) -> String {
        format!("unrelated:{}", input)
    }
}

// 5. Macro-generated code
macro_rules! create_generated_call {
    ($name:ident) => {
        pub fn $name() -> &'static str {
            "from_macro"
        }
    };
}

create_generated_call!(generated_from_macro);

// Callers:

// 1. Module paths & 2. use aliases
pub fn caller_module_paths() -> &'static str {
    let _a = internal_module::module_target_func();
    let _b = target_alias();
    let mut _map = MapAlias::new();
    _a
}

// 3. Associated functions
pub fn caller_associated_functions() {
    let worker = internal_module::Worker::associated_create();
    let _ = worker.member_action();
}

// 4. Trait methods (dynamic / generic dispatch)
pub fn caller_trait_generic<T: DataHandler>(handler: &T, val: &str) -> String {
    handler.handle_data(val)
}

// 5. Call to macro-generated function
pub fn caller_macro_target() -> &'static str {
    generated_from_macro()
}

// 6. Ambiguous method resolution
pub fn caller_ambiguous_call(unknown_ref: &FirstHandler) -> String {
    // syntactically `.handle_data()`, but without type checker looks ambiguous against 3 candidates
    unknown_ref.handle_data("input")
}

