//! SDK mode Cap'n Proto handling
//! This module provides standalone serialization without depending on prohand-capnp

use capnp::message;
use capnp::{serialize, serialize_packed};

// Use generated modules from crate root
// Note: SDK schema now uses same names as internal (ProHandCommand, ProHandStatus)
// for automatic Cap'n Proto evolution
use crate::envelope_capnp;
use crate::joint_capnp::compact_joint_state;
use crate::prohand_sdk_capnp::{pro_hand_command, pro_hand_status};

/// Error type for SDK Cap'n Proto operations
#[derive(Debug, thiserror::Error)]
pub enum SdkCapnpError {
    #[error("Cap'n Proto error: {0}")]
    Capnp(#[from] capnp::Error),
    #[error("Not in schema error: {0}")]
    NotInSchema(#[from] capnp::NotInSchema),
}

pub type Result<T> = std::result::Result<T, SdkCapnpError>;

/// Compact joint state for SDK (position + torque/velocity)
#[derive(Debug, Clone, Copy, Default)]
pub struct CompactJointState {
    pub scaled_position: i16,
    pub normalized_vel_or_tau: i16,
}

// Conversion utilities for JointState packing/unpacking
impl CompactJointState {
    /// Create a JointState from f32 values (used by GUI and application)
    pub fn from_f32(position: f32, vel_or_tau: f32) -> Self {
        let position_i16 = Self::pack_scaled_position_to_i16(position);
        let vel_or_tau_i16 = Self::pack_normalized_to_i16(vel_or_tau);

        Self { scaled_position: position_i16, normalized_vel_or_tau: vel_or_tau_i16 }
    }

    /// Convert JointState to f32 values (used by GUI and application)
    pub fn to_f32(&self) -> (f32, f32) {
        let position = Self::unpack_scaled_position_from_i16(self.scaled_position);
        let vel_or_tau = Self::unpack_normalized_from_i16(self.normalized_vel_or_tau);

        (position, vel_or_tau)
    }

    /// Joint angle in centi-degrees, the `scaledPosition` unit. One rule
    /// shared by every reference client: computed in f64, clamped to the
    /// i16 range, never wrapped, rounded half away from zero.
    fn pack_scaled_position_to_i16(position_rad: f32) -> i16 {
        Self::round_i16((position_rad as f64).to_degrees() * 100.0)
    }

    fn round_i16(value: f64) -> i16 {
        value.round().clamp(-32768.0, 32767.0) as i16
    }

    /// Unpack u16 position to f32 radians
    fn unpack_scaled_position_from_i16(packed: i16) -> f32 {
        const TO_RAD: f32 = core::f32::consts::PI / 180.0;
        let position_deg = packed as f32 * 0.01; // 0.01 degree precision
        position_deg * TO_RAD
    }

    /// [-1, 1] onto the full i16 range, the `normalizedVelOrTau` unit.
    fn pack_normalized_to_i16(normalized: f32) -> i16 {
        Self::round_i16((normalized as f64).clamp(-1.0, 1.0) * 32767.0)
    }

    /// The hand command's global speed cap, [0, 1] onto a byte; the wire
    /// default of zero does not move.
    pub fn pack_velocity_saturation(normalized: f32) -> u8 {
        ((normalized as f64).clamp(0.0, 1.0) * 255.0).round() as u8
    }

    /// Unpack velocity and torque from u16
    fn unpack_normalized_from_i16(packed: i16) -> f32 {
        packed as f32 / 32767.0
    }
}

/// Hand command (fingers only)
#[derive(Debug, Clone)]
pub struct HandCommand {
    pub timestamp: u16,
    pub uid: u16,
    pub thumb: [CompactJointState; 4],
    pub index: [CompactJointState; 4],
    pub middle: [CompactJointState; 4],
    pub ring: [CompactJointState; 4],
    pub pinky: [CompactJointState; 4],
    /// Global velocity saturation cap (0 = no cap, full speed).
    pub velocity_saturation: u8,
}

/// Wrist command
#[derive(Debug, Clone)]
pub struct WristCommand {
    pub timestamp: u16,
    pub uid: u16,
    pub wrist: [CompactJointState; 2],
}

/// The fleet-default rotary velocity, so a command published from this SDK
/// moves at the fleet-default speed rather than Cap'n Proto's 0 (= servo
/// Running Speed 0 = stop).
pub const DEFAULT_ROTARY_VELOCITY: u8 = 50;

/// Rotary motor command
#[derive(Debug, Clone, Copy)]
pub struct RotaryCommand {
    pub position: i16,
    pub torque: u16,
    /// Per-servo max-velocity cap, written to the servo's Running Speed
    /// register — 0 means the servo will not move.
    pub velocity: u8,
}

impl Default for RotaryCommand {
    fn default() -> Self {
        Self { position: 0, torque: 0, velocity: DEFAULT_ROTARY_VELOCITY }
    }
}

/// Linear motor command
#[derive(Debug, Clone, Copy, Default)]
pub struct LinearCommand {
    pub position: i16,
    pub speed: u16,
}

/// SDK serialization interface
pub struct SdkSerializer;

impl SdkSerializer {
    pub fn new() -> Self {
        Self
    }

    /// Create a ping command
    pub fn create_ping_command(&self) -> Result<Vec<u8>> {
        let mut message = message::Builder::new_default();
        let mut cmd = message.init_root::<pro_hand_command::Builder>();
        cmd.set_ping(());

        let mut buf = Vec::new();
        serialize_packed::write_message(&mut buf, &message)?;
        Ok(buf)
    }

    /// Create a rotary command
    pub fn create_rotary_command(&self, commands: [RotaryCommand; 16]) -> Result<Vec<u8>> {
        let mut message = message::Builder::new_default();
        let mut cmd = message.init_root::<pro_hand_command::Builder>();
        let mut list = cmd.reborrow().init_rotary_grp_command(16);

        for (i, rc) in commands.iter().enumerate() {
            let mut item = list.reborrow().get(i as u32);
            item.set_position(rc.position);
            item.set_torque(rc.torque);
            item.set_velocity(rc.velocity);
        }

        let mut buf = Vec::new();
        serialize_packed::write_message(&mut buf, &message)?;
        Ok(buf)
    }

    /// Create a linear command
    pub fn create_linear_command(&self, commands: [LinearCommand; 2]) -> Result<Vec<u8>> {
        let mut message = message::Builder::new_default();
        let mut cmd = message.init_root::<pro_hand_command::Builder>();
        let mut list = cmd.reborrow().init_linear_grp_command(2);

        for (i, lc) in commands.iter().enumerate() {
            let mut item = list.reborrow().get(i as u32);
            item.set_position(lc.position);
            item.set_speed(lc.speed);
        }

        let mut buf = Vec::new();
        serialize_packed::write_message(&mut buf, &message)?;
        Ok(buf)
    }

    /// Create a hand state command
    pub fn create_hand_state_command(&self, cmd: HandCommand) -> Result<Vec<u8>> {
        let mut message = message::Builder::new_default();
        let mut proto_cmd = message.init_root::<pro_hand_command::Builder>();
        let mut hand_cmd = proto_cmd.reborrow().init_hand_state_command();

        hand_cmd.set_timestamp(cmd.timestamp);
        hand_cmd.set_uid(cmd.uid);

        // Helper to fill joint array
        let fill_joints = |mut builder: capnp::struct_list::Builder<compact_joint_state::Owned>,
                           joints: &[CompactJointState; 4]| {
            for (i, joint) in joints.iter().enumerate() {
                let mut j = builder.reborrow().get(i as u32);
                j.set_scaled_position(joint.scaled_position);
                j.set_normalized_vel_or_tau(joint.normalized_vel_or_tau);
            }
        };

        fill_joints(hand_cmd.reborrow().init_thumb(4), &cmd.thumb);
        fill_joints(hand_cmd.reborrow().init_index(4), &cmd.index);
        fill_joints(hand_cmd.reborrow().init_middle(4), &cmd.middle);
        fill_joints(hand_cmd.reborrow().init_ring(4), &cmd.ring);
        fill_joints(hand_cmd.reborrow().init_pinky(4), &cmd.pinky);
        hand_cmd.set_velocity_saturation(cmd.velocity_saturation);

        let mut buf = Vec::new();
        serialize_packed::write_message(&mut buf, &message)?;
        Ok(buf)
    }

    /// Create a wrist state command
    pub fn create_wrist_state_command(&self, cmd: WristCommand) -> Result<Vec<u8>> {
        let mut message = message::Builder::new_default();
        let mut proto_cmd = message.init_root::<pro_hand_command::Builder>();
        let mut wrist_cmd = proto_cmd.reborrow().init_wrist_state_command();

        wrist_cmd.set_timestamp(cmd.timestamp);
        wrist_cmd.set_uid(cmd.uid);

        let mut wrist = wrist_cmd.init_wrist(2);
        for (i, joint) in cmd.wrist.iter().enumerate() {
            let mut j = wrist.reborrow().get(i as u32);
            j.set_scaled_position(joint.scaled_position);
            j.set_normalized_vel_or_tau(joint.normalized_vel_or_tau);
        }

        let mut buf = Vec::new();
        serialize_packed::write_message(&mut buf, &message)?;
        Ok(buf)
    }

    /// Create a hand service command (for enabling/disabling streaming).
    /// `true` maps to OnDemand (legacy semantics), `false` to Off. Continuous and
    /// filter modes are not exposed here; build the `ProHandCommand` directly
    /// if you need them.
    pub fn create_streaming_mode_command(&self, enabled: bool) -> Result<Vec<u8>> {
        let mut message = message::Builder::new_default();
        let cmd = message.init_root::<pro_hand_command::Builder>();
        let service = cmd.init_hand_request();

        // streamingMode is now a struct-with-union (Off / OnDemand / Continuous(SpaceFilter)).
        let mut sm = service.init_streaming_mode();
        if enabled {
            sm.set_on_demand(());
        } else {
            sm.set_off(());
        }

        let mut buf = Vec::new();
        serialize_packed::write_message(&mut buf, &message)?;
        Ok(buf)
    }

    /// Create a zero calibration command
    pub fn create_zero_calib_command(&self, motor_mask: [bool; 16]) -> Result<Vec<u8>> {
        let mut message = message::Builder::new_default();
        let cmd = message.init_root::<pro_hand_command::Builder>();
        let service = cmd.init_hand_request();

        // Set the zeroCalib union variant with a list of bools
        let mut mask_list = service.init_zero_calib(16);
        for (i, &enabled) in motor_mask.iter().enumerate() {
            mask_list.set(i as u32, enabled);
        }

        let mut buf = Vec::new();
        serialize_packed::write_message(&mut buf, &message)?;
        Ok(buf)
    }

    /// Create a homing command. `start = true` begins the firmware homing
    /// sequence (drives all finger + wrist joints to the firmware's neutral
    /// pose); `false` aborts a running sequence. Distinct from zero *calibration*.
    pub fn create_homing_command(&self, start: bool) -> Result<Vec<u8>> {
        let mut message = message::Builder::new_default();
        let cmd = message.init_root::<pro_hand_command::Builder>();
        let mut service = cmd.init_hand_request();
        service.set_homing(start);

        let mut buf = Vec::new();
        serialize_packed::write_message(&mut buf, &message)?;
        Ok(buf)
    }
}

/// The device frame a stamp refers to: unbound, or the control tick it was
/// taken in.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Frame {
    Unbound,
    Tick(u32),
}

/// What every status frame carries besides its body: the device clock,
/// the sequence counter, the boot count, frames dropped before this one and
/// the clock-sync state.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Header {
    pub t_device_us: u64,
    pub frame: Frame,
    pub seq: u32,
    pub boot: u16,
    pub dropped: u8,
    pub sync: u8,
}

/// One status frame off the status stream. `t_host_us` is the device clock
/// mapped onto the host's, which the driver fills once the clocks are
/// synchronised. The body stays a Cap'n Proto reader: pick the variant with
/// `which()` and read its fields zero-copy.
pub struct ProHandStatus {
    pub header: Header,
    pub t_host_us: Option<u64>,
    message: message::Reader<serialize::OwnedSegments>,
}

impl ProHandStatus {
    pub fn body(&self) -> Result<pro_hand_status::Reader<'_>> {
        Ok(self.message.get_root::<pro_hand_status::Reader>()?)
    }
}

impl std::fmt::Debug for ProHandStatus {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.debug_struct("ProHandStatus")
            .field("header", &self.header)
            .field("t_host_us", &self.t_host_us)
            .finish_non_exhaustive()
    }
}

pub fn parse_status_message(bytes: &[u8]) -> Result<ProHandStatus> {
    let message = serialize_packed::read_message(&mut &bytes[..], message::ReaderOptions::new())?;
    let status = message.get_root::<pro_hand_status::Reader>()?;
    let header = if status.has_header() {
        let h = status.get_header()?;
        let stamp = h.get_stamp()?;
        let frame = match stamp.get_frame()?.which()? {
            envelope_capnp::frame::Unbound(()) => Frame::Unbound,
            envelope_capnp::frame::Tick(tick) => Frame::Tick(tick),
        };
        Header {
            t_device_us: stamp.get_t_device_us(),
            frame,
            seq: h.get_seq(),
            boot: h.get_boot(),
            dropped: h.get_dropped(),
            sync: h.get_sync(),
        }
    } else {
        Header { t_device_us: 0, frame: Frame::Unbound, seq: 0, boot: 0, dropped: 0, sync: 0 }
    };
    let t_host_us = match status.get_t_host_us() {
        0 => None,
        us => Some(us),
    };
    Ok(ProHandStatus { header, t_host_us, message })
}

#[cfg(test)]
mod tests {
    use super::*;

    /// The integers the Python and C++ reference clients produce for the
    /// same inputs; the command fixture pins them on the wire.
    #[test]
    fn wire_integers_follow_the_shared_rounding_rule() {
        let position = |rad: f32| CompactJointState::from_f32(rad, 0.0).scaled_position;
        assert_eq!(position(0.3), 1719);
        assert_eq!(position(0.5), 2865);
        assert_eq!(position(1.0), 5730);
        assert_eq!(position(-1.0), -5730);
        assert_eq!(position(0.0), 0);
        assert_eq!(position(3.2), 18335, "past 180 degrees is clamped, not wrapped");
        assert_eq!(position(-3.2), -18335);
        assert_eq!(position(10.0), 32767, "clamped at the range end");
        let normalized = |v: f32| CompactJointState::from_f32(0.0, v).normalized_vel_or_tau;
        assert_eq!(normalized(0.3), 9830);
        assert_eq!(normalized(0.5), 16384, "16383.5 rounds away from zero");
        assert_eq!(normalized(-0.5), -16384);
        assert_eq!(normalized(1.0), 32767);
        assert_eq!(normalized(-1.0), -32767);
        assert_eq!(normalized(2.0), 32767, "clamped");
        assert_eq!(CompactJointState::pack_velocity_saturation(0.3), 77, "76.5 rounds away");
        assert_eq!(CompactJointState::pack_velocity_saturation(0.5), 128);
        assert_eq!(CompactJointState::pack_velocity_saturation(1.0), 255);
        assert_eq!(CompactJointState::pack_velocity_saturation(0.0), 0);
    }
}
