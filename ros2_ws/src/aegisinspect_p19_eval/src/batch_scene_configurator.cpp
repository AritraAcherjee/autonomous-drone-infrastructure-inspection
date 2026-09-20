#include <sstream>
#include <gz/plugin/Register.hh>
#include <gz/sim/Model.hh>
#include <gz/sim/System.hh>
#include <gz/sim/components/Model.hh>
#include <gz/sim/components/Name.hh>
#include <gz/sim/components/ParentEntity.hh>
#include <gz/sim/components/Visual.hh>
#include "aegisinspect_p19_eval/sensor_batch_certificate.h"

namespace aegisinspect::p19_eval {
class BatchSceneConfigurator final : public gz::sim::System,
  public gz::sim::ISystemPostUpdate {
 public: void PostUpdate(const gz::sim::UpdateInfo &,
    const gz::sim::EntityComponentManager &ecm) override {
    if (configured) return;
    const auto modelEntity = ecm.EntityByComponents(gz::sim::components::Model(),
      gz::sim::components::Name("p19_defect_target_001"));
    if (modelEntity == gz::sim::kNullEntity) return;
    const gz::sim::Model model(modelEntity);
    const auto linkEntity = model.LinkByName(ecm, "target_surface");
    if (linkEntity == gz::sim::kNullEntity) return;
    const auto visualEntity = ecm.EntityByComponents(gz::sim::components::Visual(),
      gz::sim::components::ParentEntity(linkEntity), gz::sim::components::Name("defect_face"));
    if (visualEntity == gz::sim::kNullEntity) return;
    std::ostringstream identity;
    identity << "{\"gt_defect_id\":\"P19-GT-DEFECT-001\",\"link\":\"target_surface\""
             << ",\"link_entity\":" << linkEntity
             << ",\"model\":\"p19_defect_target_001\",\"model_entity\":" << modelEntity
             << ",\"visual\":\"defect_face\",\"visual_entity\":" << visualEntity << "}";
    p19_set_scene_identity(identity.str().c_str()); configured = true;
  }
 private: bool configured{false};
};
}
GZ_ADD_PLUGIN(aegisinspect::p19_eval::BatchSceneConfigurator, gz::sim::System,
  gz::sim::ISystemPostUpdate)
GZ_ADD_PLUGIN_ALIAS(aegisinspect::p19_eval::BatchSceneConfigurator,
  "aegisinspect::p19_eval::BatchSceneConfigurator")
