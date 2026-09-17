#include <algorithm>
#include <array>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <mutex>

#include <gz/math/Pose3.hh>
#include <gz/math/Vector3.hh>
#include <gz/msgs/boolean.pb.h>
#include <gz/msgs/empty.pb.h>
#include <gz/msgs/pose.pb.h>
#include <gz/msgs/convert/Pose.hh>
#include <gz/plugin/Register.hh>
#include <gz/sim/EntityComponentManager.hh>
#include <gz/sim/components/AngularVelocityReset.hh>
#include <gz/sim/components/LinearVelocityReset.hh>
#include <gz/sim/Link.hh>
#include <gz/sim/Model.hh>
#include <gz/sim/System.hh>
#include <gz/sim/Util.hh>
#include <gz/transport/Node.hh>

namespace aegisinspect::sim
{
namespace
{
constexpr double kPi = 3.14159265358979323846;

constexpr double kMass = 1.5;
constexpr double kIxx = 0.0218;
constexpr double kIyy = 0.0218;
constexpr double kIzz = 0.0400;

constexpr double kGravity = 9.81;

constexpr double kPositionKp = 6.0;
constexpr double kPositionKd = 4.2;
constexpr double kOrientationKp = 0.12;
constexpr double kOrientationKd = 0.10;

constexpr double kMaxVelocity = 0.35;
constexpr double kMaxAcceleration = 0.35;
constexpr double kMaxAngularVelocity = 0.25;
constexpr double kMaxAngularAcceleration = 0.35;

constexpr double kMaxForceXY = 3.0;
constexpr double kMaxForceZ = 20.0;
constexpr double kMaxForceNorm = 20.0;

constexpr double kMaxTorqueAxis = 0.10;
constexpr double kMaxTorqueNorm = 0.15;

constexpr double kInitialHoldDuration = 3.0;
constexpr double kSegmentDuration = 3.0;
constexpr double kTrajectoryDuration = 15.0;
constexpr double kFinalHoldStart = 18.0;
constexpr double kCompleteTime = 20.0;

constexpr char kStartService[] = "/aegis/sim/internal/motion/start";
constexpr char kResetService[] = "/aegis/sim/internal/motion/reset";
constexpr char kGroundTruthTopic[] =
  "/aegis/sim/ground_truth/pose_gz";

constexpr auto kGroundTruthPeriod = std::chrono::milliseconds(10);

struct Quaternion
{
  double w{1.0};
  double x{0.0};
  double y{0.0};
  double z{0.0};
};

struct Waypoint
{
  double x;
  double y;
  double z;
  double roll;
  double pitch;
  double yaw;
};

constexpr double DegToRad(double degrees)
{
  return degrees * kPi / 180.0;
}

constexpr std::array<Waypoint, 6> kWaypoints{{
  {0.000, 0.000, 0.000, DegToRad(0),  DegToRad(0),  DegToRad(0)},
  {0.540, 0.000, 0.000, DegToRad(0),  DegToRad(0),  DegToRad(8)},
  {0.680, 0.250, 0.060, DegToRad(3),  DegToRad(5),  DegToRad(18)},
  {0.500, 0.350, 0.180, DegToRad(-4), DegToRad(7),  DegToRad(5)},
  {0.300, 0.120, 0.100, DegToRad(4),  DegToRad(-5), DegToRad(-12)},
  {0.450, 0.000, 0.000, DegToRad(0),  DegToRad(0),  DegToRad(0)},
}};

struct MotionTarget
{
  gz::math::Vector3d position{0, 0, 0};
  gz::math::Vector3d velocity{0, 0, 0};
  gz::math::Vector3d acceleration{0, 0, 0};
  Quaternion orientation{};
  gz::math::Vector3d angularVelocity{0, 0, 0};
  gz::math::Vector3d angularAcceleration{0, 0, 0};
};

Quaternion Normalize(const Quaternion &_q)
{
  const double n = std::sqrt(
    _q.w * _q.w + _q.x * _q.x + _q.y * _q.y + _q.z * _q.z);

  if (n <= 1e-15)
    return {};

  return {_q.w / n, _q.x / n, _q.y / n, _q.z / n};
}

Quaternion Conjugate(const Quaternion &_q)
{
  return {_q.w, -_q.x, -_q.y, -_q.z};
}

Quaternion Multiply(const Quaternion &_a, const Quaternion &_b)
{
  return Normalize({
    _a.w * _b.w - _a.x * _b.x - _a.y * _b.y - _a.z * _b.z,
    _a.w * _b.x + _a.x * _b.w + _a.y * _b.z - _a.z * _b.y,
    _a.w * _b.y - _a.x * _b.z + _a.y * _b.w + _a.z * _b.x,
    _a.w * _b.z + _a.x * _b.y - _a.y * _b.x + _a.z * _b.w
  });
}

Quaternion FromRpy(double roll, double pitch, double yaw)
{
  const double cr = std::cos(roll * 0.5);
  const double sr = std::sin(roll * 0.5);
  const double cp = std::cos(pitch * 0.5);
  const double sp = std::sin(pitch * 0.5);
  const double cy = std::cos(yaw * 0.5);
  const double sy = std::sin(yaw * 0.5);

  return Normalize({
    cr * cp * cy + sr * sp * sy,
    sr * cp * cy - cr * sp * sy,
    cr * sp * cy + sr * cp * sy,
    cr * cp * sy - sr * sp * cy
  });
}

Quaternion FromGazebo(const gz::math::Quaterniond &_q)
{
  return Normalize({_q.W(), _q.X(), _q.Y(), _q.Z()});
}

gz::math::Vector3d RotateVector(
  const Quaternion &_q,
  const gz::math::Vector3d &_v)
{
  const Quaternion q = Normalize(_q);

  const double tx = 2.0 * (q.y * _v.Z() - q.z * _v.Y());
  const double ty = 2.0 * (q.z * _v.X() - q.x * _v.Z());
  const double tz = 2.0 * (q.x * _v.Y() - q.y * _v.X());

  return {
    _v.X() + q.w * tx + (q.y * tz - q.z * ty),
    _v.Y() + q.w * ty + (q.z * tx - q.x * tz),
    _v.Z() + q.w * tz + (q.x * ty - q.y * tx)
  };
}

gz::math::Vector3d RotationVector(
  const Quaternion &_desired,
  const Quaternion &_current)
{
  Quaternion error = Normalize(Multiply(_desired, Conjugate(_current)));

  if (error.w < 0.0)
  {
    error.w = -error.w;
    error.x = -error.x;
    error.y = -error.y;
    error.z = -error.z;
  }

  const double vectorNorm =
    std::sqrt(error.x * error.x + error.y * error.y + error.z * error.z);

  if (vectorNorm <= 1e-12)
    return {0, 0, 0};

  const double angle =
    2.0 * std::atan2(vectorNorm, std::clamp(error.w, -1.0, 1.0));

  const double scale = angle / vectorNorm;
  return {error.x * scale, error.y * scale, error.z * scale};
}

Quaternion InterpolateShortest(
  const Quaternion &_q0,
  const Quaternion &_q1,
  double _s)
{
  Quaternion relative = Normalize(Multiply(_q1, Conjugate(_q0)));

  if (relative.w < 0.0)
  {
    relative.w = -relative.w;
    relative.x = -relative.x;
    relative.y = -relative.y;
    relative.z = -relative.z;
  }

  const double vectorNorm =
    std::sqrt(relative.x * relative.x +
              relative.y * relative.y +
              relative.z * relative.z);

  if (vectorNorm <= 1e-12)
    return Normalize(_q0);

  const double angle =
    2.0 * std::atan2(vectorNorm, std::clamp(relative.w, -1.0, 1.0));

  const double half = 0.5 * angle * _s;
  const double sinHalf = std::sin(half);
  const double invNorm = 1.0 / vectorNorm;

  Quaternion delta{
    std::cos(half),
    relative.x * invNorm * sinHalf,
    relative.y * invNorm * sinHalf,
    relative.z * invNorm * sinHalf
  };

  return Normalize(Multiply(delta, _q0));
}

void RelativeAxisAngle(
  const Quaternion &_q0,
  const Quaternion &_q1,
  gz::math::Vector3d &_axis,
  double &_angle)
{
  Quaternion relative = Normalize(Multiply(_q1, Conjugate(_q0)));

  if (relative.w < 0.0)
  {
    relative.w = -relative.w;
    relative.x = -relative.x;
    relative.y = -relative.y;
    relative.z = -relative.z;
  }

  const double vectorNorm =
    std::sqrt(relative.x * relative.x +
              relative.y * relative.y +
              relative.z * relative.z);

  if (vectorNorm <= 1e-12)
  {
    _axis = {0, 0, 0};
    _angle = 0.0;
    return;
  }

  _angle =
    2.0 * std::atan2(vectorNorm, std::clamp(relative.w, -1.0, 1.0));

  _axis = {
    relative.x / vectorNorm,
    relative.y / vectorNorm,
    relative.z / vectorNorm
  };
}

gz::math::Vector3d ClampNorm(
  const gz::math::Vector3d &_value,
  double _maximum)
{
  const double length = _value.Length();

  if (length <= _maximum || length <= 1e-15)
    return _value;

  return _value * (_maximum / length);
}

gz::math::Vector3d ApplyWorldInertia(
  const Quaternion &_orientation,
  const gz::math::Vector3d &_worldVector)
{
  const Quaternion inverse = Conjugate(Normalize(_orientation));

  const gz::math::Vector3d body =
    RotateVector(inverse, _worldVector);

  const gz::math::Vector3d bodyScaled{
    kIxx * body.X(),
    kIyy * body.Y(),
    kIzz * body.Z()
  };

  return RotateVector(_orientation, bodyScaled);
}

void MinimumJerk(
  double _u,
  double &_s,
  double &_sDot,
  double &_sDdot)
{
  const double u = std::clamp(_u, 0.0, 1.0);

  const double u2 = u * u;
  const double u3 = u2 * u;
  const double u4 = u3 * u;
  const double u5 = u4 * u;

  _s = 10.0 * u3 - 15.0 * u4 + 6.0 * u5;

  const double dsdu =
    30.0 * u2 - 60.0 * u3 + 30.0 * u4;

  const double d2sdu2 =
    60.0 * u - 180.0 * u2 + 120.0 * u3;

  _sDot = dsdu / kSegmentDuration;
  _sDdot = d2sdu2 / (kSegmentDuration * kSegmentDuration);
}
}  // namespace

class DeterministicMotionSystem final :
  public gz::sim::System,
  public gz::sim::ISystemConfigure,
  public gz::sim::ISystemPreUpdate,
  public gz::sim::ISystemPostUpdate
{
public:
  void Configure(
    const gz::sim::Entity &_entity,
    const std::shared_ptr<const sdf::Element> &,
    gz::sim::EntityComponentManager &_ecm,
    gz::sim::EventManager &) override
  {
    this->modelEntity_ = _entity;

    gz::sim::Model model(_entity);
    this->linkEntity_ = model.LinkByName(_ecm, "base_link");

    if (this->linkEntity_ == gz::sim::kNullEntity)
    {
      std::lock_guard<std::mutex> lock(this->mutex_);
      this->state_ = State::kFaultHold;
      return;
    }

    this->initialPose_ = gz::sim::worldPose(this->linkEntity_, _ecm);
    this->initialOrientation_ = FromGazebo(this->initialPose_.Rot());

    gz::sim::Link link(this->linkEntity_);
    link.EnableVelocityChecks(_ecm, true);

    const bool startAdvertised = this->transportNode_.Advertise(
      kStartService,
      &DeterministicMotionSystem::OnStart,
      this);

    const bool resetAdvertised = this->transportNode_.Advertise(
      kResetService,
      &DeterministicMotionSystem::OnReset,
      this);

    {
      std::lock_guard<std::mutex> lock(this->mutex_);

      this->controlReady_ =
        startAdvertised &&
        resetAdvertised &&
        this->groundTruthPublisher_.Valid();

      this->startPending_ = false;
      this->resetPending_ = false;
      this->state_ = State::kHoldInitial;
    }
  }

  void PreUpdate(
    const gz::sim::UpdateInfo &_info,
    gz::sim::EntityComponentManager &_ecm) override
  {
    if (_info.paused || this->linkEntity_ == gz::sim::kNullEntity)
      return;

    const double simSeconds =
      std::chrono::duration<double>(_info.simTime).count();

    bool resetNow = false;

    {
      std::lock_guard<std::mutex> lock(this->mutex_);

      if (this->resetPending_ && this->state_ == State::kComplete)
      {
        this->resetPending_ = false;
        this->startPending_ = false;
        this->epochSeconds_ = 0.0;
        this->state_ = State::kResetting;
        resetNow = true;
      }
      else if (
        this->startPending_ &&
        this->state_ == State::kHoldInitial)
      {
        this->startPending_ = false;
        this->epochSeconds_ = simSeconds;
        this->state_ = State::kInitialising;
      }
    }

    if (resetNow)
    {
      this->ResetModel(_ecm);

      {
        std::lock_guard<std::mutex> lock(this->mutex_);
        this->state_ = State::kHoldInitial;
      }

      return;
    }

    State localState;
    double epochSeconds;

    {
      std::lock_guard<std::mutex> lock(this->mutex_);
      localState = this->state_;
      epochSeconds = this->epochSeconds_;
    }

    if (localState == State::kFaultHold)
      return;

    if (localState == State::kHoldInitial)
    {
      this->ApplyControl(this->InitialTarget(), _ecm);
      return;
    }

    if (localState == State::kComplete)
    {
      this->ApplyControl(this->WaypointTarget(5), _ecm);
      return;
    }

    const double elapsed = std::max(0.0, simSeconds - epochSeconds);

    if (elapsed < kInitialHoldDuration)
    {
      {
        std::lock_guard<std::mutex> lock(this->mutex_);
        this->state_ = State::kInitialising;
      }

      this->ApplyControl(this->InitialTarget(), _ecm);
      return;
    }

    if (elapsed < kFinalHoldStart)
    {
      {
        std::lock_guard<std::mutex> lock(this->mutex_);
        this->state_ = State::kRunTrajectory;
      }

      this->ApplyControl(
        this->TrajectoryTarget(elapsed - kInitialHoldDuration),
        _ecm);
      return;
    }

    if (elapsed < kCompleteTime)
    {
      {
        std::lock_guard<std::mutex> lock(this->mutex_);
        this->state_ = State::kFinalHold;
      }

      this->ApplyControl(this->WaypointTarget(5), _ecm);
      return;
    }

    {
      std::lock_guard<std::mutex> lock(this->mutex_);
      this->state_ = State::kComplete;
    }

    this->ApplyControl(this->WaypointTarget(5), _ecm);
  }

  void PostUpdate(
    const gz::sim::UpdateInfo &_info,
    const gz::sim::EntityComponentManager &_ecm) override
  {
    if (
      _info.paused ||
      this->linkEntity_ == gz::sim::kNullEntity ||
      !this->groundTruthPublisher_.Valid())
    {
      return;
    }

    if (_info.simTime < this->nextGroundTruthPublishTime_)
      return;

    const gz::math::Pose3d pose =
      gz::sim::worldPose(this->linkEntity_, _ecm);

    gz::msgs::Pose message;
    gz::msgs::Set(&message, pose);
    message.set_name("base_link");

    const auto totalNanoseconds =
      std::chrono::duration_cast<std::chrono::nanoseconds>(
        _info.simTime).count();

    auto *stamp = message.mutable_header()->mutable_stamp();

    stamp->set_sec(
      static_cast<std::int64_t>(
        totalNanoseconds / 1000000000LL));

    stamp->set_nsec(
      static_cast<std::int32_t>(
        totalNanoseconds % 1000000000LL));

    this->groundTruthPublisher_.Publish(message);

    do
    {
      this->nextGroundTruthPublishTime_ += kGroundTruthPeriod;
    }
    while (
      this->nextGroundTruthPublishTime_ <= _info.simTime);
  }

private:
  enum class State
  {
    kHoldInitial,
    kInitialising,
    kRunTrajectory,
    kFinalHold,
    kComplete,
    kResetting,
    kFaultHold
  };

  bool OnStart(
    const gz::msgs::Empty &,
    gz::msgs::Boolean &_reply)
  {
    std::lock_guard<std::mutex> lock(this->mutex_);

    const bool accepted =
      this->controlReady_ &&
      this->state_ == State::kHoldInitial &&
      !this->startPending_;

    if (accepted)
      this->startPending_ = true;

    _reply.set_data(accepted);
    return true;
  }

  bool OnReset(
    const gz::msgs::Empty &,
    gz::msgs::Boolean &_reply)
  {
    std::lock_guard<std::mutex> lock(this->mutex_);

    const bool accepted =
      this->controlReady_ &&
      this->state_ == State::kComplete &&
      !this->resetPending_;

    if (accepted)
      this->resetPending_ = true;

    _reply.set_data(accepted);
    return true;
  }

  void ResetModel(
    gz::sim::EntityComponentManager &_ecm)
  {
    gz::sim::Model model(this->modelEntity_);

    model.SetWorldPoseCmd(_ecm, this->initialPose_);

    _ecm.SetComponentData<
      gz::sim::components::WorldLinearVelocityReset>(
        this->linkEntity_,
        gz::math::Vector3d(0, 0, 0));

    _ecm.SetComponentData<
      gz::sim::components::WorldAngularVelocityReset>(
        this->linkEntity_,
        gz::math::Vector3d(0, 0, 0));
  }

  MotionTarget InitialTarget() const
  {
    MotionTarget target;
    target.position = this->initialPose_.Pos();
    target.orientation = this->initialOrientation_;
    return target;
  }

  Quaternion WaypointOrientation(std::size_t _index) const
  {
    const auto &wp = kWaypoints.at(_index);

    return Multiply(
      FromRpy(wp.roll, wp.pitch, wp.yaw),
      this->initialOrientation_);
  }

  MotionTarget WaypointTarget(std::size_t _index) const
  {
    const auto &wp = kWaypoints.at(_index);

    MotionTarget target;
    target.position = {
      this->initialPose_.Pos().X() + wp.x,
      this->initialPose_.Pos().Y() + wp.y,
      this->initialPose_.Pos().Z() + wp.z
    };
    target.orientation = this->WaypointOrientation(_index);

    return target;
  }

  MotionTarget TrajectoryTarget(double _trajectorySeconds) const
  {
    const double bounded =
      std::clamp(_trajectorySeconds, 0.0, kTrajectoryDuration);

    const int segment =
      std::min(4, static_cast<int>(bounded / kSegmentDuration));

    const double segmentStart =
      static_cast<double>(segment) * kSegmentDuration;

    const double localTime = bounded - segmentStart;
    const double u = localTime / kSegmentDuration;

    double s = 0.0;
    double sDot = 0.0;
    double sDdot = 0.0;

    MinimumJerk(u, s, sDot, sDdot);

    const auto p0 = this->WaypointTarget(segment);
    const auto p1 = this->WaypointTarget(segment + 1);

    const gz::math::Vector3d deltaPosition =
      p1.position - p0.position;

    MotionTarget target;
    target.position = p0.position + deltaPosition * s;
    target.velocity =
      ClampNorm(deltaPosition * sDot, kMaxVelocity);

    target.acceleration =
      ClampNorm(deltaPosition * sDdot, kMaxAcceleration);

    const Quaternion q0 = p0.orientation;
    const Quaternion q1 = p1.orientation;

    target.orientation = InterpolateShortest(q0, q1, s);

    gz::math::Vector3d axis;
    double angle = 0.0;
    RelativeAxisAngle(q0, q1, axis, angle);

    target.angularVelocity =
      ClampNorm(
        axis * (angle * sDot),
        kMaxAngularVelocity);

    target.angularAcceleration =
      ClampNorm(
        axis * (angle * sDdot),
        kMaxAngularAcceleration);

    return target;
  }

  void ApplyControl(
    const MotionTarget &_target,
    gz::sim::EntityComponentManager &_ecm)
  {
    gz::sim::Link link(this->linkEntity_);

    const gz::math::Pose3d pose =
      gz::sim::worldPose(this->linkEntity_, _ecm);

    const gz::math::Vector3d linearVelocity =
      link.WorldLinearVelocity(_ecm).value_or(
        gz::math::Vector3d(0, 0, 0));

    const gz::math::Vector3d angularVelocity =
      link.WorldAngularVelocity(_ecm).value_or(
        gz::math::Vector3d(0, 0, 0));

    const Quaternion currentOrientation =
      FromGazebo(pose.Rot());

    gz::math::Vector3d force =
      _target.acceleration * kMass +
      (_target.position - pose.Pos()) * kPositionKp +
      (_target.velocity - linearVelocity) * kPositionKd +
      gz::math::Vector3d(0, 0, kMass * kGravity);

    force.X(std::clamp(force.X(), -kMaxForceXY, kMaxForceXY));
    force.Y(std::clamp(force.Y(), -kMaxForceXY, kMaxForceXY));
    force.Z(std::clamp(force.Z(), 0.0, kMaxForceZ));
    force = ClampNorm(force, kMaxForceNorm);

    const gz::math::Vector3d orientationError =
      RotationVector(_target.orientation, currentOrientation);

    const gz::math::Vector3d inertiaOmega =
      ApplyWorldInertia(currentOrientation, angularVelocity);

    gz::math::Vector3d torque =
      ApplyWorldInertia(
        currentOrientation,
        _target.angularAcceleration) +
      angularVelocity.Cross(inertiaOmega) +
      orientationError * kOrientationKp +
      (_target.angularVelocity - angularVelocity) * kOrientationKd;

    torque.X(std::clamp(
      torque.X(), -kMaxTorqueAxis, kMaxTorqueAxis));
    torque.Y(std::clamp(
      torque.Y(), -kMaxTorqueAxis, kMaxTorqueAxis));
    torque.Z(std::clamp(
      torque.Z(), -kMaxTorqueAxis, kMaxTorqueAxis));
    torque = ClampNorm(torque, kMaxTorqueNorm);

    link.AddWorldWrench(_ecm, force, torque);
  }

private:
  gz::sim::Entity modelEntity_{gz::sim::kNullEntity};
  gz::sim::Entity linkEntity_{gz::sim::kNullEntity};

  gz::math::Pose3d initialPose_;
  Quaternion initialOrientation_;

  gz::transport::Node transportNode_;

  gz::transport::Node::Publisher groundTruthPublisher_{
    this->transportNode_.Advertise<gz::msgs::Pose>(
      kGroundTruthTopic)};

  std::chrono::steady_clock::duration
    nextGroundTruthPublishTime_{0};

  mutable std::mutex mutex_;
  State state_{State::kHoldInitial};
  bool controlReady_{false};
  bool startPending_{false};
  bool resetPending_{false};
  double epochSeconds_{0.0};
};

}  // namespace aegisinspect::sim

GZ_ADD_PLUGIN(
  aegisinspect::sim::DeterministicMotionSystem,
  gz::sim::System,
  gz::sim::ISystemConfigure,
  gz::sim::ISystemPreUpdate,
  gz::sim::ISystemPostUpdate)

GZ_ADD_PLUGIN_ALIAS(
  aegisinspect::sim::DeterministicMotionSystem,
  "aegisinspect::sim::DeterministicMotionSystem")
