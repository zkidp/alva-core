use std::io::{Read, Write};
use std::net::{TcpListener, TcpStream};

pub struct HttpRequest {
    pub method: String,
    pub path: String,
    pub query: String,
    pub headers: std::collections::HashMap<String, String>,
    pub body: Vec<u8>,
}

pub fn start_server(port: i64) -> u64 {
    let addr = format!("127.0.0.1:{}", port);
    let listener = TcpListener::bind(addr).unwrap();
    Box::into_raw(Box::new(listener)) as u64
}

pub fn accept_connection(handle: u64) -> u64 {
    let listener = unsafe { &*(handle as *const TcpListener) };
    match listener.accept() {
        Ok((stream, _)) => Box::into_raw(Box::new(stream)) as u64,
        Err(_) => 0,
    }
}

pub fn read_request(stream: u64) -> HttpRequest {
    let stream = unsafe { &mut *(stream as *mut TcpStream) };
    let mut buf = Vec::new();
    let mut tmp = [0u8; 4096];
    loop {
        let n = stream.read(&mut tmp).unwrap_or(0);
        if n == 0 {
            break;
        }
        buf.extend_from_slice(&tmp[..n]);
        if buf.windows(4).any(|w| w == b"\r\n\r\n") || buf.len() > (1 << 20) {
            break;
        }
    }
    let header_end = buf
        .windows(4)
        .position(|w| w == b"\r\n\r\n")
        .map(|p| p + 4)
        .unwrap_or(buf.len());
    let text = String::from_utf8_lossy(&buf[..header_end]);
    let mut lines = text.split("\r\n");
    let request_line = lines.next().unwrap_or("");
    let mut parts = request_line.split_whitespace();
    let method = parts.next().unwrap_or("").to_string();
    let raw_path = parts.next().unwrap_or("/");
    let (path, query) = match raw_path.split_once('?') {
        Some((p, q)) => (p.to_string(), q.to_string()),
        None => (raw_path.to_string(), String::new()),
    };
    let mut content_length = 0usize;
    let mut expect_continue = false;
    let mut headers = std::collections::HashMap::new();
    for line in lines {
        if let Some((name, value)) = line.split_once(':') {
            headers.insert(name.trim().to_ascii_lowercase(), value.trim().to_string());
        }
        let lower = line.to_ascii_lowercase();
        if let Some(v) = lower.strip_prefix("content-length:") {
            content_length = v.trim().parse().unwrap_or(0);
        }
        if lower.contains("expect:") && lower.contains("100-continue") {
            expect_continue = true;
        }
    }
    if expect_continue {
        let _ = stream.write_all(b"HTTP/1.1 100 Continue\r\n\r\n");
    }
    let mut body = buf[header_end..].to_vec();
    while body.len() < content_length {
        let n = stream.read(&mut tmp).unwrap_or(0);
        if n == 0 {
            break;
        }
        body.extend_from_slice(&tmp[..n]);
    }
    body.truncate(content_length);
    HttpRequest {
        method,
        path,
        query,
        headers,
        body,
    }
}

pub fn write_response(stream: u64, status: i64, content_type: String, body: Vec<u8>) -> i64 {
    let stream = unsafe { &mut *(stream as *mut TcpStream) };
    let reason = match status {
        200 => "OK",
        201 => "Created",
        204 => "No Content",
        400 => "Bad Request",
        404 => "Not Found",
        500 => "Internal Server Error",
        _ => "OK",
    };
    let head = format!(
        "HTTP/1.1 {} {}\r\nContent-Type: {}\r\nContent-Length: {}\r\nLast-Modified: Mon, 05 Jan 2026 00:00:00 GMT\r\nConnection: close\r\n\r\n",
        status,
        reason,
        content_type,
        body.len()
    );
    let _ = stream.write_all(head.as_bytes());
    let _ = stream.write_all(&body);
    status
}

pub fn write_head_response(stream: u64, status: i64, content_length: i64) -> i64 {
    let stream = unsafe { &mut *(stream as *mut TcpStream) };
    let reason = match status {
        200 => "OK",
        204 => "No Content",
        400 => "Bad Request",
        404 => "Not Found",
        _ => "OK",
    };
    let head = format!(
        "HTTP/1.1 {} {}\r\nContent-Length: {}\r\nLast-Modified: Mon, 05 Jan 2026 00:00:00 GMT\r\nConnection: close\r\n\r\n",
        status, reason, content_length
    );
    let _ = stream.write_all(head.as_bytes());
    status
}

pub fn close_stream(stream: u64) -> i64 {
    if stream != 0 {
        unsafe {
            drop(Box::from_raw(stream as *mut TcpStream));
        }
    }
    0
}

pub fn url_decode(s: String) -> String {
    let bytes = s.as_bytes();
    let mut out = Vec::with_capacity(bytes.len());
    let mut i = 0;
    while i < bytes.len() {
        if bytes[i] == b'%' && i + 2 < bytes.len() {
            let hi = (bytes[i + 1] as char).to_digit(16);
            let lo = (bytes[i + 2] as char).to_digit(16);
            if let (Some(h), Some(l)) = (hi, lo) {
                out.push((h * 16 + l) as u8);
                i += 3;
                continue;
            }
        }
        out.push(bytes[i]);
        i += 1;
    }
    String::from_utf8_lossy(&out).to_string()
}

// 常量时间字符串比较（避免签名比较的时序侧信道）
pub fn ct_eq(a: String, b: String) -> bool {
    let ab = a.as_bytes();
    let bb = b.as_bytes();
    if ab.len() != bb.len() {
        return false;
    }
    let mut diff = 0u8;
    for i in 0..ab.len() {
        diff |= ab[i] ^ bb[i];
    }
    diff == 0
}

// ---- minimal typed filesystem primitives (v0.3 durable storage) ----
// These are the ONLY filesystem entry points the generated crate exposes.
// The commit protocol, metadata transitions, recovery and GC live in the
// alva storage modules, not here.

fn err_storage(code: &str, msg: &str) -> String {
    format!("{code}:{msg}")
}

fn random_hex() -> String {
    use std::sync::atomic::{AtomicU64, Ordering};
    static COUNTER: AtomicU64 = AtomicU64::new(0);
    let nanos = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_nanos() as u64)
        .unwrap_or(0);
    let c = COUNTER.fetch_add(1, Ordering::Relaxed);
    let x = (nanos ^ c.rotate_left(17)) ^ ((std::process::id() as u64) << 32);
    format!("{x:016x}{c:016x}")
}

fn to_hex(bytes: &[u8]) -> String {
    let mut s = String::with_capacity(bytes.len() * 2);
    for b in bytes {
        s.push_str(&format!("{b:02x}"));
    }
    s
}

pub fn fs_create_temp(dir: String, prefix: String) -> Result<String, String> {
    let dir = std::path::Path::new(&dir);
    std::fs::create_dir_all(dir)
        .map_err(|e| err_storage("E_STORAGE_002", &format!("create tmp dir: {e}")))?;
    let path = dir.join(format!("{prefix}{}.tmp", random_hex()));
    std::fs::File::create(&path)
        .map_err(|e| err_storage("E_STORAGE_002", &format!("create tmp file: {e}")))?;
    Ok(path.to_string_lossy().to_string())
}

pub fn fs_write_bytes(path: String, data: Vec<u8>) -> Result<i64, String> {
    use std::io::Write;
    let mut f = std::fs::OpenOptions::new()
        .write(true)
        .open(&path)
        .map_err(|e| err_storage("E_STORAGE_002", &format!("open for write: {e}")))?;
    f.write_all(&data)
        .map_err(|e| err_storage("E_STORAGE_002", &format!("write: {e}")))?;
    Ok(data.len() as i64)
}

pub fn fs_read_bytes(path: String) -> Result<Vec<u8>, String> {
    std::fs::read(&path).map_err(|e| err_storage("E_STORAGE_002", &format!("read: {e}")))
}

pub fn fs_read_string(path: String) -> Result<String, String> {
    std::fs::read_to_string(&path)
        .map_err(|e| err_storage("E_STORAGE_002", &format!("read text: {e}")))
}

pub fn fs_file_size(path: String) -> Result<i64, String> {
    std::fs::metadata(&path)
        .map(|m| m.len() as i64)
        .map_err(|e| err_storage("E_STORAGE_002", &format!("stat: {e}")))
}

pub fn fs_fsync_file(path: String) -> Result<i64, String> {
    std::fs::OpenOptions::new()
        .read(true)
        .write(true)
        .open(&path)
        .and_then(|f| f.sync_all())
        .map(|_| 0)
        .map_err(|e| err_storage("E_STORAGE_003", &format!("fsync file: {e}")))
}

pub fn fs_rename(src: String, dst: String) -> Result<i64, String> {
    std::fs::rename(&src, &dst).map(|_| 0).map_err(|e| {
        err_storage(
            "E_STORAGE_004",
            &format!("atomic rename {src} -> {dst}: {e}"),
        )
    })
}

pub fn fs_fsync_dir(path: String) -> Result<i64, String> {
    #[cfg(windows)]
    {
        // std::fs::File::sync_all() cannot flush directories on Windows
        // (FlushFileBuffers requires GENERIC_WRITE). Use kernel32 directly
        // with FILE_FLAG_BACKUP_SEMANTICS, which is the documented way to
        // open a directory handle and flush its metadata.
        use std::os::windows::ffi::OsStrExt;
        use std::ptr;
        const FILE_FLAG_BACKUP_SEMANTICS: u32 = 0x0200_0000;
        const GENERIC_WRITE: u32 = 0x4000_0000;
        const OPEN_EXISTING: u32 = 3;
        const INVALID_HANDLE_VALUE: isize = -1;
        #[link(name = "kernel32")]
        extern "system" {
            fn CreateFileW(
                lp_file_name: *const u16,
                dw_desired_access: u32,
                dw_share_mode: u32,
                lp_security_attributes: *mut std::ffi::c_void,
                dw_creation_disposition: u32,
                dw_flags_and_attributes: u32,
                h_template_file: *mut std::ffi::c_void,
            ) -> isize;
            fn FlushFileBuffers(h_file: isize) -> i32;
            fn CloseHandle(h_object: isize) -> i32;
        }
        let wide: Vec<u16> = std::path::Path::new(&path)
            .as_os_str()
            .encode_wide()
            .chain(std::iter::once(0))
            .collect();
        let handle = unsafe {
            CreateFileW(
                wide.as_ptr(),
                GENERIC_WRITE,
                0,
                ptr::null_mut(),
                OPEN_EXISTING,
                FILE_FLAG_BACKUP_SEMANTICS,
                ptr::null_mut(),
            )
        };
        if handle == INVALID_HANDLE_VALUE {
            return Err(err_storage(
                "E_STORAGE_003",
                &format!(
                    "fsync dir (open) {path}: {}",
                    std::io::Error::last_os_error()
                ),
            ));
        }
        let ok = unsafe { FlushFileBuffers(handle) };
        unsafe { CloseHandle(handle) };
        if ok == 0 {
            return Err(err_storage(
                "E_STORAGE_003",
                &format!(
                    "fsync dir (flush) {path}: {}",
                    std::io::Error::last_os_error()
                ),
            ));
        }
        Ok(0)
    }
    #[cfg(not(windows))]
    {
        std::fs::File::open(&path)
            .and_then(|f| f.sync_all())
            .map(|_| 0)
            .map_err(|e| err_storage("E_STORAGE_003", &format!("fsync dir: {e}")))
    }
}

pub fn fs_list_dir(path: String) -> Result<String, String> {
    let mut names = Vec::new();
    let rd = std::fs::read_dir(&path)
        .map_err(|e| err_storage("E_STORAGE_002", &format!("read dir: {e}")))?;
    for entry in rd {
        let e = entry.map_err(|e| err_storage("E_STORAGE_002", &format!("read dir entry: {e}")))?;
        names.push(e.file_name().to_string_lossy().to_string());
    }
    names.sort();
    Ok(names.join("\n"))
}

pub fn fs_exists(path: String) -> bool {
    std::path::Path::new(&path).exists()
}

pub fn fs_mkdir_p(path: String) -> Result<i64, String> {
    std::fs::create_dir_all(&path)
        .map(|_| 0)
        .map_err(|e| err_storage("E_STORAGE_002", &format!("mkdir: {e}")))
}

pub fn fs_remove(path: String) -> Result<i64, String> {
    match std::fs::remove_file(&path) {
        Ok(()) => Ok(0),
        Err(e) if e.kind() == std::io::ErrorKind::NotFound => Ok(0),
        Err(e) => Err(err_storage("E_STORAGE_002", &format!("remove: {e}"))),
    }
}

pub fn fs_remove_dir(path: String) -> Result<i64, String> {
    match std::fs::remove_dir(&path) {
        Ok(()) => Ok(0),
        Err(e) if e.kind() == std::io::ErrorKind::NotFound => Ok(0),
        Err(e) => Err(err_storage("E_STORAGE_002", &format!("remove dir: {e}"))),
    }
}

pub fn fs_env_string(name: String, default: String) -> String {
    std::env::var(&name).unwrap_or(default)
}

pub fn fs_secure_id() -> String {
    random_hex()
}

pub fn fs_sha256(data: Vec<u8>) -> String {
    use sha2::Digest;
    let mut h = sha2::Sha256::new();
    h.update(&data);
    to_hex(&h.finalize())
}

pub fn fs_sha256_file(path: String) -> Result<String, String> {
    use sha2::Digest;
    use std::io::Read;
    let mut f = std::fs::File::open(&path)
        .map_err(|e| err_storage("E_STORAGE_002", &format!("open blob: {e}")))?;
    let mut h = sha2::Sha256::new();
    let mut buf = [0u8; 65536];
    loop {
        let n = f
            .read(&mut buf)
            .map_err(|e| err_storage("E_STORAGE_002", &format!("read blob: {e}")))?;
        if n == 0 {
            break;
        }
        h.update(&buf[..n]);
    }
    Ok(to_hex(&h.finalize()))
}

// Deterministic crash failpoint: when ALVA_FAILPOINT == <name>, the process
// exits immediately so tests can verify crash consistency at each commit stage.
pub fn fs_failpoint(name: String) -> i64 {
    if let Ok(fp) = std::env::var("ALVA_FAILPOINT") {
        if fp == name.as_str() {
            eprintln!("FAILPOINT {name}");
            std::process::exit(17);
        }
    }
    0
}
