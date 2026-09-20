#include <chrono>
#include <atomic>
#include <sstream>

#include <gz/msgs/stringmsg.pb.h>
#include <gz/msgs/pose.pb.h>
#include <gz/plugin/Register.hh>
#include <gz/sim/EventManager.hh>
#include <gz/sim/Model.hh>
#include <gz/sim/System.hh>
#include <gz/sim/rendering/Events.hh>
#include <gz/sim/components/Model.hh>
#include <gz/sim/components/Name.hh>
#include <gz/sim/components/ParentEntity.hh>
#include <gz/sim/components/Visual.hh>
#include <gz/transport/Node.hh>

namespace aegisinspect::p19_eval
{
class UpdateAttestor final : public gz::sim::System,
  public gz::sim::ISystemConfigure,
  public gz::sim::ISystemPostUpdate
{
public:
  void Configure(const gz::sim::Entity &, const std::shared_ptr<const sdf::Element> &,
    gz::sim::EntityComponentManager &, gz::sim::EventManager &_eventManager) override
  {
    publisher_ = node_.Advertise<gz::msgs::StringMsg>(
      "/aegis/p19_eval/update_attestation");
    scenePublisher_ = node_.Advertise<gz::msgs::StringMsg>(
      "/aegis/p19_eval/scene_identity");
    groundTruthFramePublisher_ = node_.Advertise<gz::msgs::StringMsg>(
      "/aegis/p19_eval/ground_truth_frame_identity");
    node_.Subscribe("/aegis/sim/ground_truth/pose_gz",
      &UpdateAttestor::OnGroundTruthPose, this);
    postRenderConnection_ = _eventManager.Connect<gz::sim::events::PostRender>(
      [this]() { this->OnPostRender(); });
  }

  void PostUpdate(const gz::sim::UpdateInfo &_info,
    const gz::sim::EntityComponentManager &_ecm) override
  {
    if (!publisher_.Valid() || _info.paused)
      return;
    const auto ns = std::chrono::duration_cast<std::chrono::nanoseconds>(
      _info.simTime).count();
    latestIteration_.store(_info.iterations, std::memory_order_release);
    latestSimTimeNs_.store(ns, std::memory_order_release);

    if ((!scenePublished_ || _info.iterations % 1000 == 0) &&
        scenePublisher_.Valid())
    {
      const auto modelEntity = _ecm.EntityByComponents(
        gz::sim::components::Model(),
        gz::sim::components::Name("p19_defect_target_001"));
      if (modelEntity != gz::sim::kNullEntity)
      {
        const gz::sim::Model model(modelEntity);
        const auto linkEntity = model.LinkByName(_ecm, "target_surface");
        if (linkEntity != gz::sim::kNullEntity)
        {
          const auto visualEntity = _ecm.EntityByComponents(
            gz::sim::components::Visual(),
            gz::sim::components::ParentEntity(linkEntity),
            gz::sim::components::Name("defect_face"));
          if (visualEntity != gz::sim::kNullEntity)
          {
            gz::msgs::StringMsg scene;
            std::ostringstream identity;
            identity << "{\"gt_defect_id\":\"P19-GT-DEFECT-001\""
                     << ",\"model\":\"p19_defect_target_001\""
                     << ",\"model_entity\":" << modelEntity
                     << ",\"link\":\"target_surface\""
                     << ",\"link_entity\":" << linkEntity
                     << ",\"visual\":\"defect_face\""
                     << ",\"visual_entity\":" << visualEntity << "}";
            scene.set_data(identity.str());
            scenePublisher_.Publish(scene);
            scenePublished_ = true;
          }
        }
      }
    }
  }

private:
  void OnGroundTruthPose(const gz::msgs::Pose &_message)
  {
    if (!groundTruthFramePublisher_.Valid() || !_message.has_header() ||
        !_message.header().has_stamp() || _message.name().empty())
      return;
    const auto &stamp = _message.header().stamp();
    const auto timestampNs = stamp.sec() * 1000000000LL + stamp.nsec();
    if (timestampNs <= 0)
      return;
    gz::msgs::StringMsg identity;
    std::ostringstream value;
    value << "{\"schema\":\"aegisinspect.p19.ground_truth_frame_identity.v1\""
          << ",\"timestamp_ns\":" << timestampNs
          << ",\"pose_name\":\"" << _message.name() << "\""
          << ",\"source_topic\":\"/aegis/sim/ground_truth/pose_gz\"}";
    identity.set_data(value.str());
    groundTruthFramePublisher_.Publish(identity);
  }

  void OnPostRender()
  {
    if (!publisher_.Valid())
      return;
    const auto iteration = latestIteration_.load(std::memory_order_acquire);
    const auto simTimeNs = latestSimTimeNs_.load(std::memory_order_acquire);
    if (iteration < 1 || simTimeNs <= 0)
      return;
    const auto renderEvent = renderEventCount_.fetch_add(1) + 1;
    gz::msgs::StringMsg msg;
    std::ostringstream value;
    value << "{\"iteration\":" << iteration
          << ",\"sim_time_ns\":" << simTimeNs
          << ",\"paused\":false"
          << ",\"render_event\":" << renderEvent
          << ",\"render_event_type\":\"gz::sim::events::PostRender\"}";
    msg.set_data(value.str());
    publisher_.Publish(msg);
  }

private:
  gz::transport::Node node_;
  gz::transport::Node::Publisher publisher_;
  gz::transport::Node::Publisher scenePublisher_;
  gz::transport::Node::Publisher groundTruthFramePublisher_;
  gz::common::ConnectionPtr postRenderConnection_;
  std::atomic<std::uint64_t> latestIteration_{0};
  std::atomic<std::int64_t> latestSimTimeNs_{0};
  std::atomic<std::uint64_t> renderEventCount_{0};
  bool scenePublished_{false};
};
}

GZ_ADD_PLUGIN(aegisinspect::p19_eval::UpdateAttestor,
  gz::sim::System,
  gz::sim::ISystemConfigure,
  gz::sim::ISystemPostUpdate)
GZ_ADD_PLUGIN_ALIAS(aegisinspect::p19_eval::UpdateAttestor,
  "aegisinspect::p19_eval::UpdateAttestor")
