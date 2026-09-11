cmake_minimum_required(VERSION 3.16)
project(aegisinspect_interfaces)
find_package(ament_cmake REQUIRED)
install(DIRECTORY config DESTINATION share/${PROJECT_NAME})

ament_package()
