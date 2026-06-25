use std::sync::Mutex;

extern crate serde_json;

use tauri::Manager;
use tauri_plugin_shell::process::{CommandChild, CommandEvent};
use tauri_plugin_shell::ShellExt;

struct RecognizerSidecar {
    _child: Mutex<Option<CommandChild>>,
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_process::init())
        .plugin(tauri_plugin_shell::init())
        .setup(|app| {
            #[cfg(desktop)]
            {
                app.handle()
                    .plugin(tauri_plugin_updater::Builder::new().build())?;
                if let Err(error) = start_recognizer_sidecar(app) {
                    eprintln!("[recognizer] sidecar not started: {error}");
                }
            }
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}

#[cfg(desktop)]
fn start_recognizer_sidecar(app: &mut tauri::App) -> Result<(), Box<dyn std::error::Error>> {
    let mut command = app.shell().sidecar("binaries/recognizer")?;

    if let Some(manifest_url) = option_env!("XIANGQI_MODELS_MANIFEST") {
        command = command.env("XIANGQI_MODELS_MANIFEST", manifest_url);
    }
    if let Some(model_dir) = option_env!("XIANGQI_MODEL_DIR") {
        command = command.env("XIANGQI_MODEL_DIR", model_dir);
    }

    let (mut rx, child) = command.spawn()?;
    app.manage(RecognizerSidecar {
        _child: Mutex::new(Some(child)),
    });

    tauri::async_runtime::spawn(async move {
        while let Some(event) = rx.recv().await {
            match event {
                CommandEvent::Stdout(line) => {
                    println!("[recognizer] {}", String::from_utf8_lossy(&line).trim_end());
                }
                CommandEvent::Stderr(line) => {
                    eprintln!("[recognizer] {}", String::from_utf8_lossy(&line).trim_end());
                }
                CommandEvent::Error(error) => {
                    eprintln!("[recognizer] sidecar error: {error}");
                }
                CommandEvent::Terminated(payload) => {
                    eprintln!("[recognizer] sidecar exited: {payload:?}");
                }
                _ => {}
            }
        }
    });

    Ok(())
}
