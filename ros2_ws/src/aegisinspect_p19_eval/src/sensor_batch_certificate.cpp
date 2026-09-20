#include "aegisinspect_p19_eval/sensor_batch_certificate.h"
#include <atomic>
#include <algorithm>
#include <cstdlib>
#include <iomanip>
#include <mutex>
#include <optional>
#include <sstream>
#include <string>
#include <openssl/sha.h>
#include <gz/msgs/stringmsg.pb.h>
#include <gz/transport/Node.hh>

namespace {
constexpr const char *kSchema = "aegisinspect.p19.sensor_batch_certificate.v1";
constexpr const char *kTelemetrySchema = "aegisinspect.p19.sensor_batch_telemetry.v1";
constexpr const char *kRule = "gz-sim-10.5.0-sensors-manager-runonce-membership-v1";
constexpr const char *kInstrumentation =
  "p19-batch-hooks-v1;gz-sim=10.5.0;gz-sensors=10.0.2;gz-rendering=10.0.2;ogre=2.3.3";

std::string Hash(const void *data, std::size_t size) {
  unsigned char digest[SHA256_DIGEST_LENGTH];
  SHA256(static_cast<const unsigned char *>(data), size, digest);
  std::ostringstream out; out << std::hex << std::setfill('0');
  for (auto byte : digest) out << std::setw(2) << static_cast<unsigned int>(byte);
  return out.str();
}
std::string Quote(const std::string &value) {
  std::ostringstream out; out << '"';
  for (const unsigned char c : value) {
    if (c == '"' || c == '\\') out << '\\' << c;
    else if (c < 0x20) out << "\\u" << std::hex << std::setw(4)
                           << std::setfill('0') << static_cast<int>(c);
    else out << c;
  }
  out << '"'; return out.str();
}
std::string OperationalHash(std::int64_t stamp, const std::string &frame,
  std::uint32_t width, std::uint32_t height, const std::string &encoding,
  std::uint32_t step, const void *data, std::size_t size) {
  const auto dataHash = Hash(data, size);
  std::ostringstream json;
  json << "{\"data_sha256\":" << Quote(dataHash)
       << ",\"encoding\":" << Quote(encoding)
       << ",\"frame_id\":" << Quote(frame)
       << ",\"height\":" << height << ",\"is_bigendian\":0"
       << ",\"stamp_ns\":" << stamp << ",\"step\":" << step
       << ",\"width\":" << width << "}";
  const auto value = json.str(); return Hash(value.data(), value.size());
}
struct ImageMember {
  std::string sensor, nativeHash, operationalHash;
  std::int64_t timestamp{0};
  std::uint32_t width{0}, height{0}, step{0};
};
struct Batch {
  bool open{false}, malformed{false};
  std::uint64_t sequence{0}, updateIdentity{0};
  std::int64_t simTimeNs{0};
  std::optional<ImageMember> rgb, depth, truth;
};
thread_local Batch batch;
std::atomic<std::uint64_t> nextBatch{0}, consecutive{0};
std::mutex configMutex;
std::string sceneJson, sceneHash, calibrationHash, calibrationSensor;
bool configurationMalformed{false};
struct Telemetry {
  std::string runId;
  std::uint64_t total{0}, nonAcquisition{0}, relevant{0}, bothValid{0};
  std::uint64_t rgbdOnly{0}, truthOnly{0}, bothInvalid{0}, certificates{0};
  std::uint64_t currentStreak{0}, maxStreak{0};
  bool initialized{false}, accountingValid{true};
};
Telemetry telemetry;
gz::transport::Node node;
auto publisher = node.Advertise<gz::msgs::StringMsg>(
  "/aegis/p19_eval/sensor_batch_certificate");
auto telemetryPublisher = node.Advertise<gz::msgs::StringMsg>(
  "/aegis/p19_eval/sensor_batch_telemetry");
std::string RunId() {
  const char *value = std::getenv("P19_CERTIFICATE_RUN_ID");
  return value && *value ? value : "";
}
void Record(std::optional<ImageMember> &member, const char *sensor,
  std::int64_t stamp, const void *data, std::size_t size,
  std::uint32_t width, std::uint32_t height, std::uint32_t step,
  const char *frame, const char *rosEncoding) {
  if (!batch.open || !sensor || !data || !frame || stamp <= 0 || member) {
    batch.malformed = true; return;
  }
  ImageMember value; value.sensor = sensor; value.nativeHash = Hash(data, size);
  value.operationalHash = OperationalHash(stamp, frame, width, height,
    rosEncoding, step, data, size);
  value.timestamp = stamp; value.width = width; value.height = height; value.step = step;
  member = std::move(value);
}
}

extern "C" void p19_batch_open(std::uint64_t identity, std::int64_t time) {
  {
    std::lock_guard<std::mutex> lock(configMutex);
    const auto run = RunId();
    if (!telemetry.initialized) {
      telemetry.initialized = true;
      telemetry.runId = run;
    } else if (telemetry.runId != run) {
      telemetry.accountingValid = false;
    }
  }
  const bool leakedContext = batch.open;
  batch = Batch{}; batch.open = true; batch.sequence = ++nextBatch;
  batch.malformed = leakedContext;
  batch.updateIdentity = identity; batch.simTimeNs = time;
}
extern "C" void p19_batch_close() {
  if (!batch.open) return;
  std::lock_guard<std::mutex> lock(configMutex); const auto run = RunId();
  if (!telemetry.initialized || telemetry.runId != run) {
    telemetry.accountingValid = false;
  }
  const bool rgbdAny = batch.rgb || batch.depth;
  const bool truthGenerated = batch.truth.has_value();
  const bool any = rgbdAny || truthGenerated;
  const bool complete = batch.rgb && batch.depth && batch.truth;
  const bool sensorIdentityValid = complete &&
    batch.rgb->sensor == batch.depth->sensor &&
    batch.rgb->sensor != batch.truth->sensor;
  const bool eligibilityValid = complete && sensorIdentityValid && !batch.malformed &&
    !run.empty() && batch.updateIdentity != 0 && batch.simTimeNs > 0 &&
    !sceneHash.empty() && !calibrationHash.empty() && !configurationMalformed &&
    telemetry.accountingValid;
  bool certificateEmitted = false;
  if (eligibilityValid) {
    const auto valid = telemetry.currentStreak + 1;
    const auto id = run + ":batch:" + std::to_string(batch.sequence);
    std::ostringstream j;
    j << "{\"schema\":" << Quote(kSchema) << ",\"run_id\":" << Quote(run)
      << ",\"acquisition_batch_id\":" << Quote(id)
      << ",\"batch_sequence\":" << batch.sequence
      << ",\"consecutive_valid_index\":" << valid
      << ",\"applied_update_identity\":" << batch.updateIdentity
      << ",\"applied_sim_time_ns\":" << batch.simTimeNs
      << ",\"rgbd_sensor_id\":" << Quote(batch.rgb->sensor)
      << ",\"truth_sensor_id\":" << Quote(batch.truth->sensor)
      << ",\"native_rgb_sha256\":" << Quote(batch.rgb->nativeHash)
      << ",\"operational_rgb_sha256\":" << Quote(batch.rgb->operationalHash)
      << ",\"native_depth_sha256\":" << Quote(batch.depth->nativeHash)
      << ",\"operational_depth_sha256\":" << Quote(batch.depth->operationalHash)
      << ",\"truth_label_map_sha256\":" << Quote(batch.truth->nativeHash)
      << ",\"operational_truth_sha256\":" << Quote(batch.truth->operationalHash)
      << ",\"native_rgb_timestamp_ns\":" << batch.rgb->timestamp
      << ",\"native_depth_timestamp_ns\":" << batch.depth->timestamp
      << ",\"native_truth_timestamp_ns\":" << batch.truth->timestamp
      << ",\"rgb_width\":" << batch.rgb->width << ",\"rgb_height\":" << batch.rgb->height
      << ",\"rgb_step\":" << batch.rgb->step << ",\"rgb_encoding\":\"RGB_INT8\""
      << ",\"depth_width\":" << batch.depth->width << ",\"depth_height\":" << batch.depth->height
      << ",\"depth_step\":" << batch.depth->step << ",\"depth_encoding\":\"R_FLOAT32\""
      << ",\"truth_width\":" << batch.truth->width << ",\"truth_height\":" << batch.truth->height
      << ",\"truth_step\":" << batch.truth->step << ",\"truth_encoding\":\"RGB_INT8_LABEL_MAP\""
      << ",\"calibration_sha256\":" << Quote(calibrationHash)
      << ",\"scene_identity_sha256\":" << Quote(sceneHash)
      << ",\"gt_defect_id\":\"P19-GT-DEFECT-001\",\"target_class\":\"Honeycombing\""
      << ",\"scene_model\":\"p19_defect_target_001\",\"scene_link\":\"target_surface\""
      << ",\"scene_visual\":\"defect_face\""
      << ",\"batch_open_provenance\":\"SensorsPrivate::RunOnce:manager-runonce-open\""
      << ",\"batch_close_provenance\":\"SensorsPrivate::RunOnce:manager-runonce-return\""
      << ",\"instrumentation_identity\":" << Quote(kInstrumentation)
      << ",\"binding_rule_version\":" << Quote(kRule) << "}";
    gz::msgs::StringMsg msg; msg.set_data(j.str());
    certificateEmitted = publisher.Publish(msg);
  }

  const char *classification = "NON_ACQUISITION_BATCH";
  ++telemetry.total;
  if (!any) {
    ++telemetry.nonAcquisition;
  } else {
    ++telemetry.relevant;
    if (rgbdAny && !truthGenerated) {
      classification = "RGBD_ONLY"; ++telemetry.rgbdOnly;
    } else if (!rgbdAny && truthGenerated) {
      classification = "TRUTH_ONLY"; ++telemetry.truthOnly;
    } else if (eligibilityValid && certificateEmitted) {
      classification = "BOTH_GENERATED_VALID"; ++telemetry.bothValid;
      ++telemetry.certificates; ++telemetry.currentStreak;
      telemetry.maxStreak = std::max(telemetry.maxStreak, telemetry.currentStreak);
    } else {
      classification = "BOTH_GENERATED_INVALID"; ++telemetry.bothInvalid;
    }
    if (std::string(classification) != "BOTH_GENERATED_VALID")
      telemetry.currentStreak = 0;
  }
  consecutive.store(telemetry.currentStreak);
  if (batch.sequence != telemetry.total)
    telemetry.accountingValid = false;
  std::ostringstream t;
  t << "{\"schema\":" << Quote(kTelemetrySchema)
    << ",\"run_id\":" << Quote(telemetry.runId)
    << ",\"last_batch_sequence\":" << batch.sequence
    << ",\"last_classification\":" << Quote(classification)
    << ",\"total_manager_batches\":" << telemetry.total
    << ",\"non_acquisition_batches\":" << telemetry.nonAcquisition
    << ",\"relevant_candidate_batches\":" << telemetry.relevant
    << ",\"both_generated_valid\":" << telemetry.bothValid
    << ",\"rgbd_only\":" << telemetry.rgbdOnly
    << ",\"truth_only\":" << telemetry.truthOnly
    << ",\"both_generated_invalid\":" << telemetry.bothInvalid
    << ",\"certificate_count\":" << telemetry.certificates
    << ",\"current_consecutive_valid_streak\":" << telemetry.currentStreak
    << ",\"max_consecutive_valid_streak\":" << telemetry.maxStreak
    << ",\"accounting_valid\":" << (telemetry.accountingValid ? "true" : "false") << "}";
  if (any) {
    gz::msgs::StringMsg telemetryMsg; telemetryMsg.set_data(t.str());
    if (!telemetryPublisher.Publish(telemetryMsg))
      telemetry.accountingValid = false;
  }
  batch = Batch{};
}
extern "C" void p19_set_scene_identity(const char *json) {
  if (!json) return; std::lock_guard<std::mutex> lock(configMutex);
  const std::string value{json}; const auto hash = Hash(value.data(), value.size());
  if (!sceneHash.empty() && (sceneHash != hash || sceneJson != value)) configurationMalformed = true;
  sceneJson = value; sceneHash = hash;
}
extern "C" void p19_record_calibration(const char *sensor, const void *data, std::size_t size) {
  if (!sensor || !data || !size || !batch.open) { batch.malformed = true; return; }
  const auto hash = Hash(data, size);
  std::lock_guard<std::mutex> lock(configMutex);
  if (!calibrationHash.empty() && (calibrationHash != hash || calibrationSensor != sensor))
    configurationMalformed = true;
  calibrationSensor = sensor; calibrationHash = hash;
}
extern "C" void p19_record_rgb(const char *s, std::int64_t t, const void *d, std::size_t n,
  std::uint32_t w, std::uint32_t h, std::uint32_t step, const char *f) {
  Record(batch.rgb, s, t, d, n, w, h, step, f, "rgb8");
}
extern "C" void p19_record_depth(const char *s, std::int64_t t, const void *d, std::size_t n,
  std::uint32_t w, std::uint32_t h, std::uint32_t step, const char *f) {
  Record(batch.depth, s, t, d, n, w, h, step, f, "32FC1");
}
extern "C" void p19_record_truth(const char *s, std::int64_t t, const void *d, std::size_t n,
  std::uint32_t w, std::uint32_t h, std::uint32_t step, const char *f) {
  Record(batch.truth, s, t, d, n, w, h, step, f, "rgb8");
}
