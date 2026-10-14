use std::env;
use std::path::Path;

fn main() {
    compile_sdk_schema();
}

fn compile_sdk_schema() {
    // The public schema: PROHAND_SCHEMA_DIR when set; inside the monorepo
    // its public edition, so an in-tree build never reads a stale vendored
    // copy; in the shipped package the copy vendored beside the reference
    // clients (protocol/schema/prohand, where the Python and C++ clients
    // read it too).
    let manifest = env::var("CARGO_MANIFEST_DIR").unwrap();
    println!("cargo:rerun-if-env-changed=PROHAND_SCHEMA_DIR");
    let monorepo =
        Path::new(&manifest).join("../../../../../../schemas/capnp/schema/prohand/public");
    let schema_dir = match env::var("PROHAND_SCHEMA_DIR") {
        Ok(dir) => Path::new(&dir).to_path_buf(),
        Err(_) if monorepo.join("prohand_sdk.capnp").exists() => monorepo,
        Err(_) => Path::new(&manifest).join("../../../schema/prohand"),
    };
    let out_dir = env::var("OUT_DIR").unwrap();

    // Tell cargo to rerun this build script if schemas change
    println!("cargo:rerun-if-changed={}", schema_dir.display());

    let sdk_schema_path = schema_dir.join("prohand_sdk.capnp");
    println!("cargo:rerun-if-changed={}", sdk_schema_path.display());

    // Compile the SDK Cap'n Proto schema
    capnpc::CompilerCommand::new()
        .src_prefix(&schema_dir)
        .output_path(&out_dir)
        .file(&sdk_schema_path)
        .file(schema_dir.join("msg/alert.capnp"))
        .file(schema_dir.join("msg/calibration.capnp"))
        .file(schema_dir.join("msg/current_sense.capnp"))
        .file(schema_dir.join("msg/envelope.capnp"))
        .file(schema_dir.join("msg/hand.capnp"))
        .file(schema_dir.join("msg/imu.capnp"))
        .file(schema_dir.join("msg/joint.capnp"))
        .file(schema_dir.join("msg/linear.capnp"))
        .file(schema_dir.join("msg/rotary.capnp"))
        .file(schema_dir.join("msg/sync.capnp"))
        .file(schema_dir.join("msg/motion.capnp"))
        .run()
        .expect("Failed to compile Cap'n Proto SDK schema");

    println!("cargo:warning=Compiled SDK Cap'n Proto schema for standalone client");
}
