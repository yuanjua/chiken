use keyring::Entry;
use whoami;

const SERVICE_NAME: &str = "chiken"; // service name as requested

pub fn set_secret(value: &str) -> Result<(), String> {
    let username = whoami::username();
    let entry = Entry::new(SERVICE_NAME, &username)
        .map_err(|e| format!("Failed to create keyring entry: {}", e))?;
    entry
        .set_password(value)
        .map_err(|e| format!("Failed to set secret: {}", e))
}

pub fn get_secret() -> Result<Option<String>, String> {
    let username = whoami::username();
    let entry = Entry::new(SERVICE_NAME, &username)
        .map_err(|e| format!("Failed to create keyring entry: {}", e))?;
    match entry.get_password() {
        Ok(val) => Ok(Some(val)),
        Err(keyring::Error::NoEntry) => Ok(None),
        Err(e) => Err(format!("Failed to get secret: {}", e)),
    }
}


