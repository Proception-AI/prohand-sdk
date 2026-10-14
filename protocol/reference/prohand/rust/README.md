# ProHand Rust Client Library

High-level Rust client library for controlling ProHand robotic hands via IPC.

## Features

- **Simple API**: Easy-to-use client interfaces for service commands, streaming, and status
- **Type Safety**: Strongly typed Rust API with compile-time guarantees
- **Zero-Copy**: Efficient Cap'n Proto serialization
- **Public SDK**: only the public command set is exposed

## Installation

Add to your `Cargo.toml`:

```toml
[dependencies]
prohand-client = { path = "path/to/prohand-client" }
```

## Quick Start

```rust
use prohand_client::{ProHandServiceClient, ProHandPublisher};
use std::collections::HashMap;

fn main() -> Result<(), Box<dyn std::error::Error>> {
    // Connect to IPC endpoints
    let mut service = ProHandServiceClient::new("tcp://localhost:5555");
    service.connect()?;

    let mut publisher = ProHandPublisher::new("tcp://localhost:5556");
    publisher.connect()?;

    // Test connectivity
    service.send_ping(1000)?;

    // Enable streaming mode
    service.send_streaming_mode(true, 1000)?;

    // Send hand command
    let mut hand_pose = HashMap::new();
    hand_pose.insert("thumb".to_string(), vec![0.0, 0.5, 0.5, 0.5]);
    hand_pose.insert("index".to_string(), vec![0.0, 1.0, 1.0, 1.0]);

    publisher.send_hand_command(&hand_pose, false, 0.3, None)?;

    Ok(())
}
```

## API Overview

### ProHandServiceClient

Service client for request/reply commands (ping, calibration, mode control).

```rust
let mut client = ProHandServiceClient::new("tcp://localhost:5555");
client.connect()?;

// Send ping
client.send_ping(1000)?;

// Enable streaming mode
client.send_streaming_mode(true, 1000)?;

// Zero calibration
client.send_zero_calibration(Some(motor_id), 5000)?;
```

### ProHandPublisher

Publisher for high-frequency streaming commands (hand control, servo commands).

```rust
let mut publisher = ProHandPublisher::new("tcp://localhost:5556");
publisher.connect()?;

// Send hand command
let mut hand_pose = HashMap::new();
hand_pose.insert("index".to_string(), vec![0.0, 1.0, 1.0, 1.0]);
publisher.send_hand_command(&hand_pose, false, 0.3, None)?;

// Send rotary command (16 servos)
let positions = vec![100i16; 16];
let torques = vec![50u16; 16];
publisher.send_rotary_command(&positions, &torques)?;

// Send linear command (2 actuators)
let positions = vec![200i16; 2];
let speeds = vec![100u16; 2];
publisher.send_linear_command(&positions, &speeds)?;
```

### ProHandSubscriber

Subscriber for receiving status messages from the device.

```rust
let mut subscriber = ProHandSubscriber::new("tcp://localhost:5557");
subscriber.connect()?;

// Non-blocking receive
match subscriber.try_receive_status()? {
    Some(status) => {
        // Process status
        println!("Received: {:?}", status);
    }
    None => {
        // No message available
    }
}
```

## Status Messages

`ProHandSubscriber::receive_status` returns a `ProHandStatus`: the frame's
header, the host time the driver fills once the clocks are synchronised, and
the body as a Cap'n Proto reader. Pick the variant with `which()` and read its
fields in place.

```rust
use prohand_client::prohand_sdk_capnp::pro_hand_status;

if let Some(status) = subscriber.receive_status(Duration::from_millis(100))? {
    println!("seq {} at device {} us, host {:?} us",
        status.header.seq, status.header.t_device_us, status.t_host_us);
    if let pro_hand_status::HandJointStatus(joints) = status.body()?.which()? {
        let joints = joints?;
        // ...
    }
}
```

The `examples/quickstart.rs` program does this end to end.

## Error Handling

All methods return `Result<T, ClientError>`:

```rust
match service.send_ping(1000) {
    Ok(success) => {
        if success {
            println!("Ping successful");
        } else {
            println!("Ping timeout");
        }
    }
    Err(ClientError::Zmq(e)) => {
        eprintln!("ZMQ error: {}", e);
    }
    Err(ClientError::Capnp(e)) => {
        eprintln!("Serialization error: {}", e);
    }
    Err(e) => {
        eprintln!("Error: {}", e);
    }
}
```

## Examples

See the [examples directory](../../packaging/sdk/docs/EXAMPLES.md) for complete examples:

- Basic connection and ping
- Hand control with streaming
- Status monitoring
- Gesture playback
- Teleoperation

## Architecture

```
┌─────────────────┐         ┌──────────────────┐         ┌─────────────┐
│  Your Rust App  │◄────────┤  IPC Host        │◄────────┤   Device    │
│  (SDK Client)   │  ZMQ    │  (Prebuilt)      │   USB   │  (ProHand)  │
└─────────────────┘         └──────────────────┘         └─────────────┘

ZMQ Endpoints:
- Command (REQ/REP): tcp://localhost:5555
- Streaming (PUB/SUB): tcp://localhost:5556
- Status (PUB/SUB): tcp://localhost:5557
```

The client uses Cap'n Proto (SDK schema) for serialization. The IPC host supports both SDK and internal schemas, enabling coexistence of SDK clients and diagnostic tools.

## Dependencies

- `zeromq` - ZeroMQ in pure Rust for IPC communication
- `prohand-capnp` - Cap'n Proto message serialization (SDK schema)
- `thiserror` - Error handling

## License

See LICENSE file for details.

## Support

For support, issues, or feature requests:

- GitHub Issues: (repository URL)
- Documentation: (documentation URL)
- Email: support@proception.ai
