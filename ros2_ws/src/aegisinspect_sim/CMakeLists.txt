cmake_minimum_required(VERSION 3.22.1)
project(aegisinspect_sim)

find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(std_srvs REQUIRED)

find_package(gz-sim 10 REQUIRED)
find_package(gz-plugin 4 REQUIRED COMPONENTS register)
find_package(gz-transport 15 REQUIRED)
find_package(gz-msgs 12 REQUIRED)

add_library(aegis_deterministic_motion SHARED
  src/deterministic_motion_system.cpp
)

target_compile_features(
  aegis_deterministic_motion
  PUBLIC cxx_std_17
)

target_link_libraries(
  aegis_deterministic_motion
  PRIVATE
    gz-sim::gz-sim
    gz-plugin::register
    gz-transport::gz-transport
    gz-msgs::gz-msgs
)

add_executable(
  motion_control_node
  src/motion_control_node.cpp
)

target_compile_features(
  motion_control_node
  PUBLIC cxx_std_17
)

target_link_libraries(
  motion_control_node
  PRIVATE
    rclcpp::rclcpp
    std_srvs::std_srvs
    gz-transport::gz-transport
    gz-msgs::gz-msgs
)

install(
  TARGETS aegis_deterministic_motion
  LIBRARY DESTINATION lib
)

install(
  TARGETS motion_control_node
  RUNTIME DESTINATION lib/${PROJECT_NAME}
)

install(
  DIRECTORY config launch models worlds
  DESTINATION share/${PROJECT_NAME}
)

ament_package()
