// Prevents additional console window on Windows in release, DO NOT REMOVE!!
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::path::PathBuf;
use std::{
    env,
    sync::{Arc, Mutex},
};
use tauri::{Emitter, Manager, RunEvent};
use tauri_plugin_decorum::WebviewWindowExt;
use tauri_plugin_dialog;
use tauri_plugin_fs;
use tauri_plugin_shell::process::{CommandChild, CommandEvent};
use tauri_plugin_shell::ShellExt;
use tauri_plugin_window_state::{AppHandleExt, StateFlags};
mod secret_store;

// TODO: change pyinstaller to --onedir. refs: https://github.com/tauri-apps/tauri/discussions/3273
// Actual TODO: eliminate IPC using pytauri

#[tauri::command]
fn toggle_fullscreen(window: tauri::Window) {
    if let Ok(is_fullscreen) = window.is_fullscreen() {
        window.set_fullscreen(!is_fullscreen).unwrap();
    }
}

// Command to get the absolute path to the sidecar binary
#[tauri::command]
fn get_sidecar_path(handle: tauri::AppHandle) -> Result<String, String> {
    // In development, use the Python source
    if cfg!(debug_assertions) {
        let repo_root = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("..");
        let sidecar_path = repo_root
            .join("src")
            .join("main.py")
            .canonicalize()
            .map_err(|e| format!("Failed to resolve dev sidecar path: {}", e))?;
        let path_str = sidecar_path.to_string_lossy().to_string();
        println!("[tauri] Using development sidecar path: {}", path_str);
        return Ok(path_str);
    }

    // In production, use the bundled sidecar
    // Try to get the resource path first
    if let Ok(resource_path) = handle.path().resource_dir() {
        let bin = match env::consts::OS {
            "windows" => "chicken-core.exe",
            _ => "chicken-core",
        };
        let sidecar_path = resource_path.join(bin);
        if sidecar_path.exists() {
            println!(
                "[tauri] Using resource sidecar path: {}",
                sidecar_path.display()
            );
            return Ok(sidecar_path.to_string_lossy().to_string());
        }
    }

    // Fallback: look next to the executable
    let app_dir = env::current_exe()
        .map_err(|e| format!("Failed to get executable path: {}", e))?
        .parent()
        .ok_or("Failed to get parent directory")?
        .to_path_buf();

    let bin = match env::consts::OS {
        "windows" => "chicken-core.exe",
        _ => "chicken-core",
    };
    let path = app_dir.join(bin);

    println!("[tauri] Using fallback sidecar path: {}", path.display());
    Ok(path.to_string_lossy().to_string())
}

// Helper function to spawn the sidecar and monitor its stdout/stderr
fn spawn_and_monitor_sidecar(app_handle: tauri::AppHandle) -> Result<(), String> {
    // Check if a sidecar process already exists
    if let Some(state) = app_handle.try_state::<Arc<Mutex<Option<CommandChild>>>>() {
        let child_process = state.lock().unwrap();
        if child_process.is_some() {
            // A sidecar is already running, do not spawn a new one
            println!("[tauri] Sidecar is already running. Skipping spawn.");
            return Ok(()); // Exit early since sidecar is already running
        }
    }
    // Spawn sidecar
    let sidecar_command = app_handle
        .shell()
        .sidecar("chicken-core")
        .map_err(|e| e.to_string())?
        .env("PYTHONIOENCODING", "utf-8");
    let (mut rx, child) = sidecar_command.spawn().map_err(|e| e.to_string())?;

    // IMPORTANT: Store the child process in the app state to keep stdin pipe open
    // The child handle must stay alive for the stdin pipe to remain connected
    if let Some(state) = app_handle.try_state::<Arc<Mutex<Option<CommandChild>>>>() {
        *state.lock().unwrap() = Some(child);
        println!("[tauri] Sidecar spawned and child handle stored (stdin pipe active)");
    } else {
        return Err("Failed to access app state".to_string());
    }

    // Spawn an async task to handle sidecar communication
    tauri::async_runtime::spawn(async move {
        while let Some(event) = rx.recv().await {
            match event {
                CommandEvent::Stdout(line_bytes) => {
                    let line = String::from_utf8_lossy(&line_bytes);
                    println!("Sidecar stdout: {}", line);
                    // Emit the line to the frontend
                    app_handle
                        .emit("sidecar-stdout", line.to_string())
                        .expect("Failed to emit sidecar stdout event");
                }
                CommandEvent::Stderr(line_bytes) => {
                    let line = String::from_utf8_lossy(&line_bytes);
                    eprintln!("Sidecar stderr: {}", line);
                    // Emit the error line to the frontend
                    app_handle
                        .emit("sidecar-stderr", line.to_string())
                        .expect("Failed to emit sidecar stderr event");
                }
                _ => {}
            }
        }
    });

    Ok(())
}

// Define a command to shutdown sidecar process
#[tauri::command]
fn shutdown_sidecar(app_handle: tauri::AppHandle) -> Result<String, String> {
    println!("[tauri] Received command to shutdown sidecar.");
    // Access the sidecar process state
    if let Some(state) = app_handle.try_state::<Arc<Mutex<Option<CommandChild>>>>() {
        let mut child_process = state
            .lock()
            .map_err(|_| "[tauri] Failed to acquire lock on sidecar process.")?;

        if let Some(process) = child_process.take() {
            // Attempt to gracefully terminate the process
            match process.kill() {
                Ok(_) => {
                    println!("[tauri] Sidecar process terminated successfully.");
                    Ok("Sidecar process terminated successfully.".to_string())
                }
                Err(err) => {
                    println!("[tauri] Failed to kill sidecar process: {}", err);
                    Err(format!("Failed to kill sidecar process: {}", err))
                }
            }
        } else {
            println!("[tauri] No active sidecar process to shutdown.");
            Err("No active sidecar process to shutdown.".to_string())
        }
    } else {
        Err("Sidecar process state not found.".to_string())
    }
}

// Define a command to start sidecar process.
#[tauri::command]
fn start_sidecar(app_handle: tauri::AppHandle) -> Result<String, String> {
    println!("[tauri] Received command to start sidecar.");
    spawn_and_monitor_sidecar(app_handle)?;
    Ok("Sidecar spawned and monitoring started.".to_string())
}

// Secret store commands
#[tauri::command]
fn set_secret(value: String) -> Result<(), String> {
    secret_store::set_secret(&value)
}

#[tauri::command]
fn get_secret() -> Result<Option<String>, String> {
    secret_store::get_secret()
}

#[tauri::command]
fn get_backend_url() -> Result<String, String> {
    // TODO: spawn on random port
    Ok("http://localhost:8009".to_string())
}

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_store::Builder::new().build())
        .plugin(tauri_plugin_window_state::Builder::new().build())
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_decorum::init())
        .plugin(tauri_plugin_fs::init())
        .plugin(tauri_plugin_dialog::init())
        .setup(|app| {
            // Store the initial sidecar process in the app state
            app.manage(Arc::new(Mutex::new(None::<CommandChild>)));
            // Clone the app handle for use elsewhere
            let app_handle = app.handle().clone();
            // Spawn the Python sidecar on startup
            println!("[tauri] Creating sidecar...");
            spawn_and_monitor_sidecar(app_handle).ok();
            println!("[tauri] Sidecar spawned and monitoring started.");

            // Create a custom titlebar for main window
            // On Windows this will hide decoration and render custom window controls
            // On macOS it expects a hiddenTitle: true and titleBarStyle: overlay
            let main_window = app.get_webview_window("main").unwrap();
            main_window
                .create_overlay_titlebar()
                .expect("[tauri] Failed to create overlay titlebar");

            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            start_sidecar,
            shutdown_sidecar,
            toggle_fullscreen,
            get_sidecar_path,
            set_secret,
            get_secret,
            get_backend_url,
        ])
        .build(tauri::generate_context!())
        .expect("Error while running tauri application")
        .run(|app_handle, event| match event {
            RunEvent::ExitRequested { .. } => {
                println!("[tauri] App exit requested. Attempting to shutdown sidecar...");
                if let Err(e) = app_handle.save_window_state(StateFlags::all()) {
                    println!("[tauri] Failed to save window state: {}", e);
                }

                // Try to gracefully shutdown the sidecar
                if let Some(state) = app_handle.try_state::<Arc<Mutex<Option<CommandChild>>>>() {
                    let mut child_process = state.lock().unwrap();
                    if let Some(process) = child_process.take() {
                        match process.kill() {
                            Ok(_) => {
                                println!("[tauri] Sidecar terminated successfully on app exit")
                            }
                            Err(e) => {
                                println!("[tauri] Failed to terminate sidecar on app exit: {}", e)
                            }
                        }
                    } else {
                        println!("[tauri] No active sidecar to terminate");
                    }
                } else {
                    println!("[tauri] Sidecar state not found during exit");
                }
            }
            _ => {}
        });
}
