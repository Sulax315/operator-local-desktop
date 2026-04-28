use std::sync::Mutex;
use std::time::Duration;
use tauri::{AppHandle, Manager};
use tauri_plugin_shell::{
    process::{CommandChild, CommandEvent},
    ShellExt,
};

const BACKEND_HOST: &str = "127.0.0.1";
const BACKEND_PORT: &str = "8092";

#[allow(dead_code)]
struct BackendSidecar(Mutex<Option<CommandChild>>);

fn spawn_backend(app: &AppHandle) -> Result<CommandChild, String> {
    let sidecar = app
        .shell()
        .sidecar("backend_app")
        .map_err(|err| format!("failed to create backend sidecar command: {err}"))?
        .args(["--host", BACKEND_HOST, "--port", BACKEND_PORT]);

    let (mut rx, child) = sidecar
        .spawn()
        .map_err(|err| format!("failed to spawn backend sidecar: {err}"))?;

    tauri::async_runtime::spawn(async move {
        while let Some(event) = rx.recv().await {
            match event {
                CommandEvent::Stdout(line) => {
                    println!("[backend_app] {}", String::from_utf8_lossy(&line));
                }
                CommandEvent::Stderr(line) => {
                    eprintln!("[backend_app] {}", String::from_utf8_lossy(&line));
                }
                CommandEvent::Terminated(payload) => {
                    eprintln!("[backend_app] terminated: {:?}", payload);
                    break;
                }
                _ => {}
            }
        }
    });

    Ok(child)
}

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .setup(|app| {
            let child = spawn_backend(app.handle())?;
            app.manage(BackendSidecar(Mutex::new(Some(child))));
            std::thread::sleep(Duration::from_millis(750));
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running Operator Local desktop app");
}
