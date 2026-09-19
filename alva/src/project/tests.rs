use super::*;
use std::sync::atomic::{AtomicUsize, Ordering};

struct Fixture(PathBuf);

impl Fixture {
    fn new() -> Self {
        static NEXT: AtomicUsize = AtomicUsize::new(0);
        let path = std::env::temp_dir().join(format!(
            "alva manifest tests {} {}",
            std::process::id(),
            NEXT.fetch_add(1, Ordering::Relaxed)
        ));
        std::fs::create_dir(&path).unwrap();
        Self(path)
    }

    fn write(&self, path: &str, text: &str) -> PathBuf {
        let path = self.0.join(path);
        std::fs::create_dir_all(path.parent().unwrap()).unwrap();
        std::fs::write(&path, text).unwrap();
        path
    }
}

impl Drop for Fixture {
    fn drop(&mut self) {
        std::fs::remove_dir_all(&self.0).unwrap();
    }
}

fn source(name: &str) -> String {
    format!("(module (name \"{name}\") (version \"0.1.0\"))")
}

#[test]
fn toml_strings_comments_and_module_declaration_order() {
    let fixture = Fixture::new();
    let manifest = fixture.write(
        "alva.toml",
        "[project] # comment\r\nname = 'legacy'\r\n[modules]\r\n'z.last' = 'src/z # =.alva' # comment\r\n\"a.first\" = \"src/a\\u0020file.alva\"\r\n",
    );
    let project = load_project(&manifest).unwrap();
    assert_eq!(project.modules[0].0, "z.last");
    assert_eq!(project.modules[1].0, "a.first");
    assert!(project.modules[0].1.ends_with("src/z # =.alva"));
    assert!(project.modules[1].1.ends_with("src/a file.alva"));
}

#[test]
fn malformed_fields_are_rejected_with_manifest_context() {
    let fixture = Fixture::new();
    for document in [
        "[project]\nname = 'a'\nname = 'b'\n[modules]\n'm' = 'm.alva'\n",
        "[project]\nname = 'a'\n[modules]\n'm' = 'a.alva'\n'm' = 'b.alva'\n",
        "[project]\nname = 'a'\n[modules]\n'm' = 'm.alva'\n[dependencies]\nx = 'x.toml'\nx = 'y.toml'\n",
        "[project]\nname = 'a'\nunknown = 1\n[modules]\n'm' = 'm.alva'\n",
        "[project]\nname = 'a'\n[modules]\n'm' = 'm.alva'\n[dependencies]\nx = { path = 'x.toml' }\n",
        "[library]\nname = 'a'\n[modules]\n'm' = 'm.alva'\n",
        "[project]\nname = 'a'\n[library]\nname = 'b'\n[modules]\n'm' = 'm.alva'\n",
    ] {
        let manifest = fixture.write("alva.toml", document);
        let error = load_project(&manifest).err().expect("invalid document accepted");
        assert!(error.contains("alva.toml"), "{error}");
    }
}

#[test]
fn local_paths_with_at_signs_are_not_remote_git_addresses() {
    let base = Path::new(".");
    let manifest = Path::new("alva.toml");
    for value in [
        "../name@example/alva.lib.toml",
        r"C:\Users\name@example\alva.lib.toml",
    ] {
        assert!(dependency_path(base, manifest, "lib", value).is_ok());
    }
    for value in [
        "",
        "https://example.org/lib.toml",
        "git+https://example.org/lib",
        "git@example.org:lib",
    ] {
        let error = dependency_path(base, manifest, "lib", value).unwrap_err();
        assert!(error.contains("alva.toml dependency 'lib'"), "{error}");
    }
}

#[test]
fn canonical_library_identity_preserves_ownership_and_source_bytes() {
    let fixture = Fixture::new();
    let manifest = fixture.write(
        "app/alva.toml",
        "[project]\nname = 'app'\n[modules]\n'app.module' = 'main.alva'\n[dependencies]\nfirst = '../lib/alva.lib.toml'\nsecond = '../lib/../lib/alva.lib.toml'\n",
    );
    fixture.write("app/main.alva", &source("app.module"));
    let library_manifest = fixture.write(
        "lib/alva.lib.toml",
        "[library]\nname = 'library owner'\n[modules]\n'library.value' = 'value.alva'\n",
    );
    let original = format!(";; CRLF source\r\n{}\r\n", source("library.value"));
    let library_source = fixture.write("lib/value.alva", &original);
    let project = load_project(&manifest).unwrap();
    let modules = check_project(&project).unwrap_or_else(|ds| panic!("{ds:?}"));
    assert_eq!(modules.len(), 2);
    let library = &modules[1];
    assert_eq!(
        library.origin,
        ModuleOrigin::Library {
            name: "library owner".into(),
            manifest_path: std::fs::canonicalize(library_manifest).unwrap(),
        }
    );
    assert_eq!(
        std::fs::canonicalize(library.source_path.as_ref().unwrap()).unwrap(),
        std::fs::canonicalize(&library_source).unwrap()
    );
    assert_eq!(std::fs::read(library_source).unwrap(), original.as_bytes());
}

#[cfg(unix)]
#[test]
fn symlink_library_identity_is_canonical() {
    let fixture = Fixture::new();
    let manifest = fixture.write(
        "app/alva.toml",
        "[project]\nname = 'app'\n[modules]\n'app.module' = 'main.alva'\n[dependencies]\nfirst = '../lib/alva.lib.toml'\nsecond = '../alias/alva.lib.toml'\n",
    );
    fixture.write("app/main.alva", &source("app.module"));
    fixture.write(
        "lib/alva.lib.toml",
        "[library]\nname = 'lib'\n[modules]\n'lib.value' = 'value.alva'\n",
    );
    fixture.write("lib/value.alva", &source("lib.value"));
    std::os::unix::fs::symlink(fixture.0.join("lib"), fixture.0.join("alias")).unwrap();
    let project = load_project(&manifest).unwrap();
    assert_eq!(
        check_project(&project)
            .unwrap_or_else(|ds| panic!("{ds:?}"))
            .len(),
        2
    );
}

#[test]
fn source_changes_are_read_again_with_same_project_object() {
    let fixture = Fixture::new();
    let manifest = fixture.write(
        "app/alva.toml",
        "[project]\nname = 'app'\n[modules]\n'app.module' = 'main.alva'\n[dependencies]\nlib = '../lib/alva.lib.toml'\n",
    );
    fixture.write("app/main.alva", &source("app.module"));
    fixture.write(
        "lib/alva.lib.toml",
        "[library]\nname = 'lib'\n[modules]\n'lib.value' = 'value.alva'\n",
    );
    fixture.write("lib/value.alva", &source("lib.value"));
    let project = load_project(&manifest).unwrap();
    assert!(check_project(&project).is_ok());
    fixture.write("lib/value.alva", &source("changed.name"));
    let diagnostics = check_project(&project)
        .err()
        .expect("cached library source");
    assert!(diagnostics[0]
        .message
        .contains("declares module 'changed.name'"));
}
