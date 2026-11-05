//! This is the entrypoint for Lake's inference engine. This file should contain as little logic as
//! possible. This should serve only as a small wrapper creating an entrypoint around `lib.rs`.

use std::thread::sleep;
use std::time::Duration;

fn main() {
    sleep(Duration::new(0, 500000000));
    engine::hello();
    ggml_rs::hello();
    tensor_io::hello();
}
