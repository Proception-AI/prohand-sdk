use std::collections::HashMap;
use std::future::Future;
use std::sync::{Mutex, MutexGuard, OnceLock, PoisonError};
use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};

use futures::channel::mpsc::Receiver;
use tokio::runtime::{Handle, Runtime};
use zeromq::{PubSocket, ReqSocket, Socket, SocketEvent, SocketRecv, SocketSend, SubSocket};

// Generated SDK Cap'n Proto modules (must be at crate root for cross-references to work)
pub mod prohand_sdk_capnp {
    include!(concat!(env!("OUT_DIR"), "/prohand_sdk_capnp.rs"));
}

pub mod calibration_capnp {
    include!(concat!(env!("OUT_DIR"), "/msg/calibration_capnp.rs"));
}

pub mod alert_capnp {
    include!(concat!(env!("OUT_DIR"), "/msg/alert_capnp.rs"));
}

pub mod sync_capnp {
    include!(concat!(env!("OUT_DIR"), "/msg/sync_capnp.rs"));
}

pub mod motion_capnp {
    include!(concat!(env!("OUT_DIR"), "/msg/motion_capnp.rs"));
}

pub mod envelope_capnp {
    include!(concat!(env!("OUT_DIR"), "/msg/envelope_capnp.rs"));
}

pub mod hand_capnp {
    include!(concat!(env!("OUT_DIR"), "/msg/hand_capnp.rs"));
    // CalibrationPhase moved to calibration.capnp — re-export here so the
    // generated hand_capnp.rs cross-references resolve.
    pub use super::calibration_capnp::CalibrationPhase;
}

pub mod imu_capnp {
    include!(concat!(env!("OUT_DIR"), "/msg/imu_capnp.rs"));
}

pub mod current_sense_capnp {
    include!(concat!(env!("OUT_DIR"), "/msg/current_sense_capnp.rs"));
}

pub mod joint_capnp {
    include!(concat!(env!("OUT_DIR"), "/msg/joint_capnp.rs"));
}

pub mod rotary_capnp {
    include!(concat!(env!("OUT_DIR"), "/msg/rotary_capnp.rs"));
}

pub mod linear_capnp {
    include!(concat!(env!("OUT_DIR"), "/msg/linear_capnp.rs"));
}

// SDK Cap'n Proto serialization
mod sdk_capnp;
pub use sdk_capnp::parse_status_message;
use sdk_capnp::SdkSerializer;
pub use sdk_capnp::{
    CompactJointState, Frame, HandCommand, Header, LinearCommand, ProHandStatus, RotaryCommand,
    WristCommand, DEFAULT_ROTARY_VELOCITY,
};

#[derive(thiserror::Error, Debug)]
pub enum ClientError {
    #[error("ZMQ error: {0}")]
    Zmq(#[from] zeromq::ZmqError),

    #[error("Cap'n Proto error: {0}")]
    CapnpSdk(#[from] sdk_capnp::SdkCapnpError),

    #[error("Invalid argument: {0}")]
    InvalidArgument(String),
    #[error("Operation timed out")]
    Timeout,
}

pub type Result<T> = std::result::Result<T, ClientError>;

/// Bound on `connect`: zmq.rs retries a refused endpoint forever.
const CONNECT_TIMEOUT: Duration = Duration::from_secs(5);

/// One runtime for every client in the process. zmq.rs serves each peer from
/// a task it spawns, and those tasks need a worker thread of their own: on a
/// current-thread runtime they would only run while the caller's future is
/// pending, and a publish is ready at once.
fn runtime() -> &'static Runtime {
    static RUNTIME: OnceLock<Runtime> = OnceLock::new();
    RUNTIME.get_or_init(|| {
        tokio::runtime::Builder::new_multi_thread()
            .worker_threads(1)
            .thread_name("prohand-client")
            .enable_all()
            .build()
            .expect("tokio runtime for the ProHand client")
    })
}

/// Drives `f` to completion on the client runtime. A caller inside another
/// tokio runtime cannot block its thread, so the wait moves to a scoped
/// thread; everyone else blocks in place.
fn run<F>(f: F) -> F::Output
where
    F: Future + Send,
    F::Output: Send,
{
    if Handle::try_current().is_err() {
        runtime().block_on(f)
    } else {
        std::thread::scope(|s| {
            s.spawn(|| runtime().block_on(f)).join().expect("client runtime thread")
        })
    }
}

fn lock<T>(m: &Mutex<T>) -> MutexGuard<'_, T> {
    m.lock().unwrap_or_else(PoisonError::into_inner)
}

fn not_connected(what: &str) -> ClientError {
    ClientError::InvalidArgument(format!("{what} not connected"))
}

/// `timeout_ms < 0` waits forever, as libzmq's `ZMQ_RCVTIMEO` did.
fn reply_timeout(timeout_ms: i32) -> Option<Duration> {
    u64::try_from(timeout_ms).ok().map(Duration::from_millis)
}

/// What a socket does once connected, before it is handed out. Spelled with
/// `impl Future + Send` rather than `async fn`: generic callers run it on the
/// shared runtime, which needs the `Send` bound an `async fn` cannot state.
#[allow(clippy::manual_async_fn)]
trait Ready: Socket {
    fn ready(&mut self) -> impl Future<Output = Result<()>> + Send {
        async { Ok(()) }
    }
}

impl Ready for ReqSocket {}

impl Ready for PubSocket {}

impl Ready for SubSocket {
    #[allow(clippy::manual_async_fn)]
    fn ready(&mut self) -> impl Future<Output = Result<()>> + Send {
        async { Ok(self.subscribe("").await?) }
    }
}

/// One socket and its endpoint. zmq.rs reconnects nothing by itself: after a
/// transport error or a disconnect the socket is dropped here and opened
/// again on the next use, within `CONNECT_TIMEOUT`.
struct Link<S: Ready> {
    endpoint: String,
    socket: Option<S>,
    events: Option<Receiver<SocketEvent>>,
    wanted: bool,
}

impl<S: Ready> Link<S> {
    fn new(endpoint: String) -> Self {
        Self { endpoint, socket: None, events: None, wanted: false }
    }

    async fn open(&mut self) -> Result<()> {
        let mut socket = S::new();
        let events = socket.monitor();
        tokio::time::timeout(CONNECT_TIMEOUT, socket.connect(&self.endpoint))
            .await
            .map_err(|_| ClientError::Timeout)??;
        socket.ready().await?;
        self.socket = Some(socket);
        self.events = Some(events);
        Ok(())
    }

    fn close(&mut self) {
        self.socket = None;
        self.events = None;
    }

    /// The socket, opened again after a disconnect or a dropped error.
    async fn socket(&mut self, what: &str) -> Result<&mut S> {
        if !self.wanted {
            return Err(not_connected(what));
        }
        if let Some(events) = &mut self.events {
            while let Ok(event) = events.try_recv() {
                if matches!(event, SocketEvent::Disconnected(_)) {
                    self.socket = None;
                }
            }
        }
        if self.socket.is_none() {
            self.open().await?;
        }
        Ok(self.socket.as_mut().expect("opened above"))
    }
}

// Unified serializer abstraction
enum Serializer {
    Sdk(SdkSerializer),
}

impl Serializer {
    fn new() -> Self {
        Serializer::Sdk(SdkSerializer::new())
    }

    fn create_ping_command(&self) -> Result<Vec<u8>> {
        match self {
            Serializer::Sdk(sdk) => Ok(sdk.create_ping_command()?),
        }
    }

    fn create_zero_calib_command(&self, mask: [bool; 16]) -> Result<Vec<u8>> {
        match self {
            Serializer::Sdk(sdk) => Ok(sdk.create_zero_calib_command(mask)?),
        }
    }

    fn create_streaming_mode_command(&self, enabled: bool) -> Result<Vec<u8>> {
        match self {
            Serializer::Sdk(sdk) => Ok(sdk.create_streaming_mode_command(enabled)?),
        }
    }

    fn create_homing_command(&self, start: bool) -> Result<Vec<u8>> {
        match self {
            Serializer::Sdk(sdk) => Ok(sdk.create_homing_command(start)?),
        }
    }

    fn create_rotary_command(&self, commands: [RotaryCommand; 16]) -> Result<Vec<u8>> {
        match self {
            Serializer::Sdk(sdk) => Ok(sdk.create_rotary_command(commands)?),
        }
    }

    fn create_linear_command(&self, commands: [LinearCommand; 2]) -> Result<Vec<u8>> {
        match self {
            Serializer::Sdk(sdk) => Ok(sdk.create_linear_command(commands)?),
        }
    }

    fn create_hand_state_command(&self, cmd: HandCommand) -> Result<Vec<u8>> {
        match self {
            Serializer::Sdk(sdk) => Ok(sdk.create_hand_state_command(cmd)?),
        }
    }

    fn create_wrist_state_command(&self, cmd: WristCommand) -> Result<Vec<u8>> {
        match self {
            Serializer::Sdk(sdk) => Ok(sdk.create_wrist_state_command(cmd)?),
        }
    }
}

/// REQ/REP service client (ping, streaming mode, zero calibration, homing)
pub struct ProHandServiceClient {
    link: Mutex<Link<ReqSocket>>,
    serializer: Serializer,
}

impl ProHandServiceClient {
    pub fn new(command_endpoint: impl Into<String>) -> Self {
        Self { link: Mutex::new(Link::new(command_endpoint.into())), serializer: Serializer::new() }
    }

    pub fn connect(&mut self) -> Result<()> {
        let link = &mut *lock(&self.link);
        link.wanted = true;
        run(link.open())
    }

    pub fn disconnect(&mut self) {
        let link = &mut *lock(&self.link);
        link.wanted = false;
        link.close();
    }

    /// One request and its reply. `Ok(false)` is a reply that did not arrive
    /// within `timeout_ms`. A REQ socket with a request in flight cannot send
    /// the next one, so after a timeout or an error the socket is dropped and
    /// the next call opens a fresh one; a late reply has nothing to answer.
    fn round_trip(&self, bytes: Vec<u8>, timeout_ms: i32) -> Result<bool> {
        let link = &mut *lock(&self.link);
        let timeout = reply_timeout(timeout_ms);
        let outcome = run(async {
            let sock = link.socket("Service client").await?;
            sock.send(bytes.into()).await?;
            let reply = match timeout {
                Some(timeout) => match tokio::time::timeout(timeout, sock.recv()).await {
                    Ok(reply) => reply,
                    Err(_) => return Ok(false),
                },
                None => sock.recv().await,
            };
            reply?;
            Ok(true)
        });
        if !matches!(outcome, Ok(true)) {
            link.socket = None;
        }
        outcome
    }

    pub fn send_ping(&self, timeout_ms: i32) -> Result<bool> {
        let bytes = self.serializer.create_ping_command()?;
        self.round_trip(bytes, timeout_ms)
    }

    pub fn send_zero_calibration(&self, motor_id: Option<usize>, timeout_ms: i32) -> Result<bool> {
        let mut mask = [false; 16];
        if let Some(id) = motor_id {
            if id >= 16 {
                return Err(ClientError::InvalidArgument("motor_id must be 0..15".into()));
            }
            mask[id] = true;
        } else {
            mask.fill(true);
        }
        let bytes = self.serializer.create_zero_calib_command(mask)?;
        self.round_trip(bytes, timeout_ms)
    }

    pub fn send_streaming_mode(&self, enabled: bool, timeout_ms: i32) -> Result<bool> {
        let bytes = self.serializer.create_streaming_mode_command(enabled)?;
        self.round_trip(bytes, timeout_ms)
    }

    /// Start (`start = true`) or abort (`false`) the firmware homing sequence —
    /// drives all finger + wrist joints to the firmware's neutral pose. Distinct
    /// from zero *calibration* (`send_zero_calibration`).
    pub fn send_homing(&self, start: bool, timeout_ms: i32) -> Result<bool> {
        let bytes = self.serializer.create_homing_command(start)?;
        self.round_trip(bytes, timeout_ms)
    }
}

/// PUB client for streaming commands
pub struct ProHandPublisher {
    hand: Mutex<Link<PubSocket>>,
    wrist: Mutex<Link<PubSocket>>,
    serializer: Serializer,
}

impl ProHandPublisher {
    pub fn new(
        hand_streaming_endpoint: impl Into<String>,
        wrist_streaming_endpoint: impl Into<String>,
    ) -> Self {
        Self {
            hand: Mutex::new(Link::new(hand_streaming_endpoint.into())),
            wrist: Mutex::new(Link::new(wrist_streaming_endpoint.into())),
            serializer: Serializer::new(),
        }
    }

    pub fn connect(&mut self) -> Result<()> {
        for link in [&self.hand, &self.wrist] {
            let link = &mut *lock(link);
            link.wanted = true;
            run(link.open())?;
        }
        Ok(())
    }

    pub fn disconnect(&mut self) {
        for link in [&self.hand, &self.wrist] {
            let link = &mut *lock(link);
            link.wanted = false;
            link.close();
        }
    }

    /// zmq.rs queues per subscriber without blocking and drops what a full
    /// queue cannot take, so a publish never waits.
    fn publish(&self, link: &Mutex<Link<PubSocket>>, bytes: Vec<u8>) -> Result<bool> {
        let link = &mut *lock(link);
        let outcome = run(async {
            link.socket("Publisher").await?.send(bytes.into()).await?;
            Ok(true)
        });
        if outcome.is_err() {
            link.socket = None;
        }
        outcome
    }

    /// Send a rotary command at the fleet-default velocity cap
    /// (DEFAULT_ROTARY_VELOCITY, matching RotaryCommand::default()).
    pub fn send_rotary_command(&self, positions: &[i16], torques: &[u16]) -> Result<bool> {
        self.send_rotary_command_with_velocity(positions, torques, &[DEFAULT_ROTARY_VELOCITY; 16])
    }

    /// Send a rotary command with explicit per-servo max-velocity caps.
    /// A velocity of 0 is written to the servo's Running Speed register as-is,
    /// which means the servo will not move.
    pub fn send_rotary_command_with_velocity(
        &self,
        positions: &[i16],
        torques: &[u16],
        velocities: &[u8],
    ) -> Result<bool> {
        if positions.len() != 16 || torques.len() != 16 || velocities.len() != 16 {
            return Err(ClientError::InvalidArgument(
                "positions, torques and velocities must have length 16".into(),
            ));
        }
        let mut arr: [RotaryCommand; 16] = [RotaryCommand::default(); 16];
        for i in 0..16 {
            arr[i] = RotaryCommand {
                position: positions[i],
                torque: torques[i],
                velocity: velocities[i],
            };
        }
        let bytes = self.serializer.create_rotary_command(arr)?;
        self.publish(&self.hand, bytes)
    }

    pub fn send_linear_command(&self, positions: &[i16], speeds: &[u16]) -> Result<bool> {
        if positions.len() != 2 || speeds.len() != 2 {
            return Err(ClientError::InvalidArgument(
                "positions and speeds must have length 2".into(),
            ));
        }
        let mut arr: [LinearCommand; 2] = [LinearCommand::default(); 2];
        for i in 0..2 {
            arr[i] = LinearCommand { position: positions[i], speed: speeds[i] };
        }
        let bytes = self.serializer.create_linear_command(arr)?;
        self.publish(&self.wrist, bytes)
    }

    /// Send hand command (fingers only).
    ///
    /// Data keys: "thumb","index","middle","ring","pinky" with vectors of positions.
    /// Positions are radians by default (set degrees=true to pass degrees).
    pub fn send_hand_command(
        &self,
        data: &HashMap<String, Vec<f32>>,
        degrees: bool,
        torque_level: f32,
    ) -> Result<bool> {
        self.send_hand_command_with_velocity(data, degrees, torque_level, 1.0)
    }

    /// Send hand command with the global speed cap in [0, 1], as the Python
    /// and C++ reference clients take it; the wire default of zero does not
    /// move.
    pub fn send_hand_command_with_velocity(
        &self,
        data: &HashMap<String, Vec<f32>>,
        degrees: bool,
        torque_level: f32,
        velocity_saturation: f32,
    ) -> Result<bool> {
        let velocity_saturation = CompactJointState::pack_velocity_saturation(velocity_saturation);
        let to_rad = |v: f32| if degrees { v.to_radians() } else { v };

        let mut thumb = [CompactJointState::default(); 4];
        let mut index = [CompactJointState::default(); 4];
        let mut middle = [CompactJointState::default(); 4];
        let mut ring = [CompactJointState::default(); 4];
        let mut pinky = [CompactJointState::default(); 4];

        let torque = torque_level;

        let fill_finger = |dst: &mut [CompactJointState; 4], src: Option<&Vec<f32>>| {
            for (i, slot) in dst.iter_mut().enumerate() {
                let pos = src.and_then(|v| v.get(i)).copied().unwrap_or(0.0);
                let pos = to_rad(pos);
                *slot = CompactJointState::from_f32(pos, torque);
            }
        };

        fill_finger(&mut thumb, data.get("thumb"));
        fill_finger(&mut index, data.get("index"));
        fill_finger(&mut middle, data.get("middle"));
        fill_finger(&mut ring, data.get("ring"));
        fill_finger(&mut pinky, data.get("pinky"));

        // timestamp and uid
        let ts_ms = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap_or(Duration::from_millis(0))
            .as_millis() as u64;
        let timestamp = ts_ms as u16;
        let uid = 1;

        // Send hand command (fingers only)
        let hand_cmd =
            HandCommand { timestamp, uid, thumb, index, middle, ring, pinky, velocity_saturation };

        let bytes = self.serializer.create_hand_state_command(hand_cmd)?;
        self.publish(&self.hand, bytes)
    }

    /// Send wrist command.
    ///
    /// Positions are radians by default (set degrees=true to pass degrees).
    /// wrist_vel_norm: Normalized velocities for 2 wrist DOFs [-1, 1]. Defaults to [1.0, 1.0] if None.
    pub fn send_wrist_command(
        &self,
        positions: &[f32],
        wrist_vel_norm: Option<[f32; 2]>,
        degrees: bool,
    ) -> Result<bool> {
        if positions.len() != 2 {
            return Err(ClientError::InvalidArgument("exactly 2 wrist positions".into()));
        }

        let to_rad = |v: f32| if degrees { v.to_radians() } else { v };

        let mut wrist = [CompactJointState::default(); 2];
        let vel = wrist_vel_norm.unwrap_or([1.0, 1.0]);
        for i in 0..2 {
            let pos = positions.get(i).copied().unwrap_or(0.0);
            let pos = to_rad(pos);
            let mut js = CompactJointState::from_f32(pos, 0.0);
            js.normalized_vel_or_tau =
                CompactJointState::from_f32(0.0, vel[i]).normalized_vel_or_tau;
            wrist[i] = js;
        }

        // timestamp and uid
        let ts_ms = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap_or(Duration::from_millis(0))
            .as_millis() as u64;
        let timestamp = ts_ms as u16;
        let uid = 1;

        let wrist_cmd = WristCommand { timestamp, uid, wrist };

        let bytes = self.serializer.create_wrist_state_command(wrist_cmd)?;
        self.publish(&self.wrist, bytes)
    }
}

/// SUB client for receiving status
pub struct ProHandSubscriber {
    link: Mutex<Link<SubSocket>>,
    reconnect_after: Duration,
    last_frame: Mutex<Instant>,
}

/// Default for [`ProHandSubscriber::reconnect_after`].
pub const DEFAULT_RECONNECT_AFTER: Duration = Duration::from_secs(5);

impl ProHandSubscriber {
    pub fn new(status_endpoint: impl Into<String>) -> Self {
        Self {
            link: Mutex::new(Link::new(status_endpoint.into())),
            reconnect_after: DEFAULT_RECONNECT_AFTER,
            last_frame: Mutex::new(Instant::now()),
        }
    }

    /// How long the stream may stay silent before the socket is opened again.
    /// A SUB socket in zmq.rs cannot tell a quiet publisher from one that went
    /// away: a lost peer leaves no event and `recv` waits forever. The driver
    /// publishes status continuously, so silence of this length is treated as
    /// a lost host.
    pub fn reconnect_after(mut self, silence: Duration) -> Self {
        self.reconnect_after = silence;
        self
    }

    pub fn connect(&mut self) -> Result<()> {
        let link = &mut *lock(&self.link);
        link.wanted = true;
        *lock(&self.last_frame) = Instant::now();
        run(link.open())
    }

    pub fn disconnect(&mut self) {
        let link = &mut *lock(&self.link);
        link.wanted = false;
        link.close();
    }

    /// Non-blocking receive; returns Ok(None) if no message available
    pub fn try_receive_status(&self) -> Result<Option<ProHandStatus>> {
        self.receive_status(Duration::ZERO)
    }

    /// Blocking receive; returns Ok(None) when nothing arrives within `timeout`
    pub fn receive_status(&self, timeout: Duration) -> Result<Option<ProHandStatus>> {
        let link = &mut *lock(&self.link);
        let last_frame = &mut *lock(&self.last_frame);
        if link.socket.is_some() && last_frame.elapsed() >= self.reconnect_after {
            link.socket = None;
            *last_frame = Instant::now();
        }
        let received: Result<Option<Vec<u8>>> = run(async {
            let sock = link.socket("Subscriber").await?;
            match tokio::time::timeout(timeout, sock.recv()).await {
                Ok(message) => Ok(Some(
                    message?
                        .try_into()
                        .map_err(|e: &str| ClientError::InvalidArgument(e.into()))?,
                )),
                Err(_) => Ok(None),
            }
        });
        match &received {
            Ok(Some(_)) => *last_frame = Instant::now(),
            Ok(None) => {}
            Err(_) => link.socket = None,
        }
        // A frame that does not decode is that frame's fault, not the socket's:
        // the error goes up and the next frame is read from the same socket.
        match received? {
            Some(bytes) => Ok(Some(parse_status_message(&bytes)?)),
            None => Ok(None),
        }
    }
}

#[cfg(test)]
mod tests {
    use std::sync::atomic::{AtomicBool, Ordering};
    use std::sync::{mpsc, Arc};
    use std::thread::{self, JoinHandle};

    use zeromq::RepSocket;

    use super::*;

    /// Serves `serve` on its own thread and runtime until `stop` is raised.
    /// Binds `endpoint`, or an ephemeral port when it is empty, and returns
    /// what it bound.
    fn serve<S, F, Fut>(endpoint: &str, stop: Arc<AtomicBool>, serve: F) -> (String, JoinHandle<()>)
    where
        S: Socket + 'static,
        F: FnOnce(S, Arc<AtomicBool>) -> Fut + Send + 'static,
        Fut: Future<Output = ()>,
    {
        let endpoint = if endpoint.is_empty() {
            "tcp://127.0.0.1:0".to_string()
        } else {
            endpoint.to_string()
        };
        let (tx, rx) = mpsc::channel();
        let handle = thread::spawn(move || {
            tokio::runtime::Builder::new_current_thread().enable_all().build().unwrap().block_on(
                async {
                    let mut socket = S::new();
                    let bound = socket.bind(&endpoint).await.unwrap();
                    tx.send(bound.to_string()).unwrap();
                    serve(socket, stop).await;
                },
            );
        });
        (rx.recv().unwrap(), handle)
    }

    /// A REP that echoes every request, the `delayed`-th one after 300 ms.
    async fn echo(mut rep: RepSocket, stop: Arc<AtomicBool>, delayed: usize) {
        let mut n = 0;
        while !stop.load(Ordering::Relaxed) {
            let Ok(Ok(request)) = tokio::time::timeout(Duration::from_millis(50), rep.recv()).await
            else {
                continue;
            };
            n += 1;
            if n == delayed {
                tokio::time::sleep(Duration::from_millis(300)).await;
            }
            let _ = rep.send(request).await;
        }
    }

    fn never() -> Arc<AtomicBool> {
        Arc::new(AtomicBool::new(false))
    }

    /// A packed `ProHandStatus::pong` with `seq` in its header, as the driver
    /// would publish it.
    fn pong_bytes(seq: u32) -> Vec<u8> {
        let mut message = capnp::message::Builder::new_default();
        let mut status = message.init_root::<prohand_sdk_capnp::pro_hand_status::Builder>();
        status.set_pong(());
        status.set_t_host_us(5_000 + u64::from(seq));
        let mut header = status.init_header();
        header.set_seq(seq);
        header.init_stamp().set_t_device_us(1_000 + u64::from(seq));
        let mut bytes = Vec::new();
        capnp::serialize_packed::write_message(&mut bytes, &message).unwrap();
        bytes
    }

    #[test]
    fn ping_round_trips_and_a_late_reply_does_not_answer_the_next_request() {
        let (endpoint, _server) = serve("", never(), |rep, stop| echo(rep, stop, 2));
        let mut client = ProHandServiceClient::new(endpoint);
        client.connect().unwrap();

        assert!(client.send_ping(2000).unwrap());
        assert!(!client.send_ping(50).unwrap());
        assert!(client.send_streaming_mode(true, 2000).unwrap());
        assert!(client.send_ping(2000).unwrap());
    }

    #[test]
    fn service_calls_before_connect_are_an_error() {
        let client = ProHandServiceClient::new("tcp://127.0.0.1:1");
        assert!(matches!(client.send_ping(10), Err(ClientError::InvalidArgument(_))));
    }

    #[test]
    fn the_service_client_follows_a_restarted_host() {
        let stop = never();
        let (endpoint, server) = serve("", stop.clone(), |rep, stop| echo(rep, stop, 0));
        let mut client = ProHandServiceClient::new(endpoint.clone());
        client.connect().unwrap();
        assert!(client.send_ping(2000).unwrap());

        stop.store(true, Ordering::Relaxed);
        server.join().unwrap();
        let (_, _server) = serve(&endpoint, never(), |rep, stop| echo(rep, stop, 0));

        let recovered = (0..20).any(|_| client.send_ping(500).unwrap_or(false));
        assert!(recovered, "no reply from the restarted host");
    }

    #[test]
    fn subscriber_receives_published_frames() {
        let stop = never();
        let (endpoint, _server) =
            serve("", stop.clone(), |mut publisher: PubSocket, stop| async move {
                while !stop.load(Ordering::Relaxed) {
                    let _ = publisher.send(pong_bytes(42).into()).await;
                    tokio::time::sleep(Duration::from_millis(10)).await;
                }
            });
        let mut subscriber = ProHandSubscriber::new(endpoint);
        subscriber.connect().unwrap();

        let status = subscriber.receive_status(Duration::from_secs(2)).unwrap().unwrap();
        stop.store(true, Ordering::Relaxed);
        assert_eq!(status.header.seq, 42);
        assert_eq!(status.header.t_device_us, 1_042);
        assert_eq!(status.t_host_us, Some(5_042));
        assert!(matches!(
            status.body().unwrap().which(),
            Ok(prohand_sdk_capnp::pro_hand_status::Pong(()))
        ));
    }

    #[test]
    fn the_subscriber_follows_a_restarted_publisher() {
        fn beacon(
            seq: u32,
        ) -> impl FnOnce(PubSocket, Arc<AtomicBool>) -> std::pin::Pin<Box<dyn Future<Output = ()>>>
        {
            move |mut publisher, stop| {
                Box::pin(async move {
                    while !stop.load(Ordering::Relaxed) {
                        let _ = publisher.send(pong_bytes(seq).into()).await;
                        tokio::time::sleep(Duration::from_millis(10)).await;
                    }
                })
            }
        }
        let stop = never();
        let (endpoint, server) = serve("", stop.clone(), beacon(1));
        let mut subscriber =
            ProHandSubscriber::new(endpoint.clone()).reconnect_after(Duration::from_millis(300));
        subscriber.connect().unwrap();
        let first = subscriber.receive_status(Duration::from_secs(2)).unwrap().unwrap();
        assert_eq!(first.header.seq, 1);

        stop.store(true, Ordering::Relaxed);
        server.join().unwrap();
        let stop = never();
        let (_, _server) = serve(&endpoint, stop.clone(), beacon(2));

        let recovered = (0..20).any(|_| {
            matches!(subscriber.receive_status(Duration::from_millis(100)), Ok(Some(s)) if s.header.seq == 2)
        });
        stop.store(true, Ordering::Relaxed);
        assert!(recovered, "no frame from the restarted publisher");
    }

    #[test]
    fn published_frames_reach_a_subscriber() {
        let (tx, rx) = mpsc::channel::<Vec<u8>>();
        let (endpoint, _server) = serve("", never(), move |mut sub: SubSocket, _stop| async move {
            sub.subscribe("").await.unwrap();
            while let Ok(message) = sub.recv().await {
                let bytes: Vec<u8> = message.try_into().unwrap();
                if tx.send(bytes).is_err() {
                    break;
                }
            }
        });
        let mut publisher = ProHandPublisher::new(endpoint.clone(), endpoint);
        publisher.connect().unwrap();
        let expected = SdkSerializer::new()
            .create_linear_command([LinearCommand { position: 7, speed: 9 }; 2])
            .unwrap();

        let mut received = None;
        for _ in 0..200 {
            assert!(publisher.send_linear_command(&[7, 7], &[9, 9]).unwrap());
            if let Ok(bytes) = rx.recv_timeout(Duration::from_millis(10)) {
                received = Some(bytes);
                break;
            }
        }
        assert_eq!(
            received.as_deref(),
            Some(expected.as_slice()),
            "the frame never left the socket"
        );
    }

    #[test]
    fn publisher_sends_without_a_subscriber() {
        // A peer that subscribes to nothing takes no frame, so the publish
        // has nowhere to go and still returns at once.
        let (endpoint, _server) = serve("", never(), |mut sub: SubSocket, stop| async move {
            while !stop.load(Ordering::Relaxed) {
                let _ = tokio::time::timeout(Duration::from_millis(20), sub.recv()).await;
            }
        });
        let mut publisher = ProHandPublisher::new(endpoint.clone(), endpoint);
        publisher.connect().unwrap();
        assert!(publisher.send_wrist_command(&[0.0, 0.0], None, false).unwrap());
    }

    #[test]
    fn calls_from_inside_a_tokio_runtime_do_not_panic() {
        let (endpoint, _server) = serve("", never(), |rep, stop| echo(rep, stop, 0));
        let rt = tokio::runtime::Builder::new_current_thread().enable_all().build().unwrap();
        let ok = rt.block_on(async {
            let mut client = ProHandServiceClient::new(endpoint);
            client.connect().unwrap();
            client.send_ping(2000).unwrap()
        });
        assert!(ok);
    }
}
