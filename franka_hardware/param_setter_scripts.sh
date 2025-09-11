
# Full collision behaviour
ros2 service call /param_service_server/set_full_collision_behavior franka_msgs/srv/SetFullCollisionBehavior "{
  lower_torque_thresholds_acceleration: [35, 35, 32, 32, 30, 25, 23], 
  upper_torque_thresholds_acceleration: [45, 45, 40, 40, 35, 30, 28],  
  lower_torque_thresholds_nominal: [35, 35, 32, 32, 30, 25, 23], 
  upper_torque_thresholds_nominal: [45, 45, 40, 40, 35, 30, 28],  
  lower_force_thresholds_acceleration: [35, 35, 35, 25, 25, 25], 
  upper_force_thresholds_acceleration: [50, 50, 50, 35, 35, 35],  
  lower_force_thresholds_nominal: [35, 35, 35, 25, 25, 25], 
  upper_force_thresholds_nominal: [70, 70, 70, 45, 45, 45]}"

# Joint stiffness
ros2 service call /param_service_server/set_joint_stiffness franka_msgs/srv/SetJointStiffness "{
  joint_stiffness: [6000, 6000, 6000, 5000, 5000, 3500, 3000]
}"

