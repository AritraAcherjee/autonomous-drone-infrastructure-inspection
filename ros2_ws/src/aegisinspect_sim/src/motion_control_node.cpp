#include <memory>
#include <string>

#include <gz/msgs/boolean.pb.h>
#include <gz/msgs/empty.pb.h>
#include <gz/transport/Node.hh>

#include <rclcpp/rclcpp.hpp>
#include <std_srvs/srv/trigger.hpp>

namespace
{
constexpr char kRosStartService[] = "/aegis/sim/motion/start";
constexpr char kRosResetService[] = "/aegis/sim/motion/reset";

constexpr char kGazeboStartService[] =
  "/aegis/sim/internal/motion/start";

constexpr char kGazeboResetService[] =
  "/aegis/sim/internal/motion/reset";

constexpr unsigned int kGazeboServiceTimeoutMs = 1000;
}

class MotionControlNode final : public rclcpp::Node
{
public:
  MotionControlNode()
  : rclcpp::Node("motion_control_node")
  {
    this->startService_ =
      this->create_service<std_srvs::srv::Trigger>(
        kRosStartService,
        [this](
          const std::shared_ptr<
            std_srvs::srv::Trigger::Request>,
          std::shared_ptr<
            std_srvs::srv::Trigger::Response> response)
        {
          this->ForwardTrigger(
            kGazeboStartService,
            "START",
            *response);
        });

    this->resetService_ =
      this->create_service<std_srvs::srv::Trigger>(
        kRosResetService,
        [this](
          const std::shared_ptr<
            std_srvs::srv::Trigger::Request>,
          std::shared_ptr<
            std_srvs::srv::Trigger::Response> response)
        {
          this->ForwardTrigger(
            kGazeboResetService,
            "RESET",
            *response);
        });
  }

private:
  void ForwardTrigger(
    const std::string &_gazeboService,
    const std::string &_operation,
    std_srvs::srv::Trigger::Response &_response)
  {
    gz::msgs::Empty request;
    gz::msgs::Boolean reply;

    bool serviceResult = false;

    const bool executed = this->gazeboNode_.Request(
      _gazeboService,
      request,
      kGazeboServiceTimeoutMs,
      reply,
      serviceResult);

    if (!executed)
    {
      _response.success = false;
      _response.message =
        _operation +
        " timed out waiting for the Gazebo motion system.";
      return;
    }

    if (!serviceResult)
    {
      _response.success = false;
      _response.message =
        _operation +
        " Gazebo service execution failed.";
      return;
    }

    _response.success = reply.data();

    if (reply.data())
    {
      _response.message =
        _operation + " accepted.";
    }
    else
    {
      _response.message =
        _operation +
        " rejected by the deterministic motion state machine.";
    }
  }

private:
  gz::transport::Node gazeboNode_;

  rclcpp::Service<std_srvs::srv::Trigger>::SharedPtr
    startService_;

  rclcpp::Service<std_srvs::srv::Trigger>::SharedPtr
    resetService_;
};

int main(int argc, char **argv)
{
  rclcpp::init(argc, argv);

  rclcpp::spin(
    std::make_shared<MotionControlNode>());

  rclcpp::shutdown();
  return 0;
}
