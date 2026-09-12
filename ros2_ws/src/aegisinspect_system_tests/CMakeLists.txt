cmake_minimum_required(VERSION 3.16)
project(aegisinspect_system_tests)
find_package(ament_cmake REQUIRED)
install(PROGRAMS scripts/smoke_check.py DESTINATION lib/${PROJECT_NAME})
install(PROGRAMS scripts/depth_check.py DESTINATION lib/${PROJECT_NAME})

if(BUILD_TESTING)
  find_package(ament_cmake_pytest REQUIRED)
  ament_add_pytest_test(foundation_contracts test/test_foundation.py TIMEOUT 60)
  ament_add_pytest_test(simulated_depth test/test_simulated_depth.py TIMEOUT 60)
endif()

ament_package()
