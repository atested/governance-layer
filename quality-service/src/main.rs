use quality_service::config::Config;
use quality_service::service::{run_loop, run_once};
use std::env;

fn main() {
    let once = env::args().any(|arg| arg == "--once");
    let config = match Config::from_env() {
        Ok(config) => config,
        Err(err) => {
            eprintln!("{err}");
            std::process::exit(2);
        }
    };
    let result = if once {
        run_once(&config)
    } else {
        run_loop(config)
    };
    if let Err(err) = result {
        eprintln!("{err}");
        std::process::exit(1);
    }
}
