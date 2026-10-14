//! Connect to a running ProHand driver, ping it, turn streaming on, send one
//! open-hand command, and print the status frames that come back.
//!
//! ```text
//! cargo run --example quickstart -- tcp://127.0.0.1
//! ```
//!
//! The left hand's default TCP ports: 5562 commands (REQ/REP), 5561 status
//! (PUB/SUB), 5563 hand streaming and 5564 wrist streaming (PUB/SUB); the
//! right hand's are 5572, 5571, 5573 and 5574.

use std::collections::HashMap;
use std::time::{Duration, Instant};

use prohand_client::prohand_sdk_capnp::pro_hand_status;
use prohand_client::{ProHandPublisher, ProHandServiceClient, ProHandSubscriber};

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let host = std::env::args().nth(1).unwrap_or_else(|| "tcp://127.0.0.1".to_string());

    let mut service = ProHandServiceClient::new(format!("{host}:5562"));
    service.connect()?;
    if !service.send_ping(1000)? {
        return Err("no reply from the driver within 1 s".into());
    }
    println!("driver answered the ping");

    let mut subscriber = ProHandSubscriber::new(format!("{host}:5561"));
    subscriber.connect()?;
    let mut publisher = ProHandPublisher::new(format!("{host}:5563"), format!("{host}:5564"));
    publisher.connect()?;

    if !service.send_streaming_mode(true, 1000)? {
        return Err("the driver did not acknowledge streaming mode within 1 s".into());
    }
    // The first status frame shows the subscriptions are up; a setpoint sent
    // before that is dropped by the PUB socket. Streaming is a stream: the
    // setpoint goes out on every pass, not once.
    let open: HashMap<String, Vec<f32>> = ["thumb", "index", "middle", "ring", "pinky"]
        .iter()
        .map(|finger| (finger.to_string(), vec![0.0; 4]))
        .collect();

    let until = Instant::now() + Duration::from_secs(3);
    let mut frames = 0u32;
    while Instant::now() < until {
        let Some(status) = subscriber.receive_status(Duration::from_millis(200))? else { continue };
        publisher.send_hand_command(&open, false, 0.3)?;
        frames += 1;
        if frames % 50 == 1 {
            let body = status.body()?;
            let variant = match body.which()? {
                pro_hand_status::HandJointStatus(_) => "hand joints",
                pro_hand_status::WristJointStatus(_) => "wrist joints",
                pro_hand_status::HandObservedState(_) => "observed state",
                pro_hand_status::Alert(_) => "alert",
                _ => "other",
            };
            println!(
                "seq {} device {} us host {:?} us: {variant}",
                status.header.seq, status.header.t_device_us, status.t_host_us
            );
        }
    }
    println!("{frames} status frames in 3 s");

    service.send_streaming_mode(false, 1000)?;
    Ok(())
}
