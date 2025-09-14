import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (DeclareLaunchArgument, ExecuteProcess, IncludeLaunchDescription,
                            Shutdown)
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import Command, FindExecutable, LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare
from launch_ros.parameter_descriptions import ParameterValue
import yaml
import json


def load_yaml(package_name, file_path):
    package_path = get_package_share_directory(package_name)
    absolute_file_path = os.path.join(package_path, file_path)

    try:
        with open(absolute_file_path, 'r') as file:
            return yaml.safe_load(file)
    except EnvironmentError:
        print(f"[ERROR] Failed to load YAML from {absolute_file_path}")
        return None
    else:
        print(f"[INFO] Successfully loaded {absolute_file_path}")


def generate_launch_description():
    robot_ip_parameter_name = 'robot_ip'
    use_fake_hardware_parameter_name = 'use_fake_hardware'
    load_gripper_parameter_name = 'load_gripper'
    fake_sensor_commands_parameter_name = 'fake_sensor_commands'
    com_port_parameter_name = 'com_port'

    robot_ip = LaunchConfiguration(robot_ip_parameter_name)
    use_fake_hardware = LaunchConfiguration(use_fake_hardware_parameter_name)
    load_gripper = LaunchConfiguration(load_gripper_parameter_name)
    fake_sensor_commands = LaunchConfiguration(fake_sensor_commands_parameter_name)
    com_port = LaunchConfiguration(com_port_parameter_name)

    # Command-line arguments
    db_arg = DeclareLaunchArgument(
        'db', default_value='False', description='Database flag'
    )

    robot_arg = DeclareLaunchArgument(
        robot_ip_parameter_name,
        description='Hostname or IP address of the robot.')

    use_fake_hardware_arg = DeclareLaunchArgument(
        use_fake_hardware_parameter_name,
        default_value='false',
        description='Use fake hardware')

    load_gripper_arg = DeclareLaunchArgument(
        load_gripper_parameter_name,
        default_value='true',
        description='Use Robotiq Gripper as an end-effector')
    
    fake_sensor_commands_arg = DeclareLaunchArgument(
        fake_sensor_commands_parameter_name,
        default_value='false',
        description="Fake sensor commands. Only valid when '{}' is true".format(
            use_fake_hardware_parameter_name))

    com_port_arg = DeclareLaunchArgument(
        com_port_parameter_name,
        default_value='/dev/ttyUSB1',
        description='Port for communicating with Robotiq hardware')

    # Robot description - combine both Franka and Robotiq
    franka_xacro_file = os.path.join(get_package_share_directory('franka_robotiq_description'), 'urdf',
                                     'franka_robotiq.urdf.xacro')
    robot_description_config = Command([
        FindExecutable(name='xacro'),
        ' ', franka_xacro_file,
        ' robot_ip:=', robot_ip,
        ' use_fake_hardware:=', use_fake_hardware,
        ' fake_sensor_commands:=', fake_sensor_commands,
        ' com_port:=', com_port
    ])

    robot_description = {
        'robot_description': robot_description_config,
        'publish_robot_description': True
    }

    # SRDF
    srdf_path = os.path.join(get_package_share_directory('franka_robotiq_moveit_config'),
                            'config', 'franka_robotiq.srdf')
    with open(srdf_path, 'r') as f:
        srdf_content = f.read()
    robot_description_semantic = {
        'robot_description_semantic': ParameterValue(srdf_content, value_type=str)
    }

    # Kinematics
    kinematics_yaml = load_yaml(
        'franka_robotiq_moveit_config', 'config/kinematics.yaml'
    )

    # Planning pipeline
    ompl_planning_pipeline_config = {
        'move_group': {
            'planning_plugin': 'ompl_interface/OMPLPlanner',
            'request_adapters': 'default_planner_request_adapters/AddTimeOptimalParameterization '
                                'default_planner_request_adapters/ResolveConstraintFrames '
                                'default_planner_request_adapters/FixWorkspaceBounds '
                                'default_planner_request_adapters/FixStartStateBounds '
                                'default_planner_request_adapters/FixStartStateCollision '
                                'default_planner_request_adapters/FixStartStatePathConstraints',
            'start_state_max_bounds_error': 0.1,
        }
    }
    ompl_planning_yaml = load_yaml(
        'franka_moveit_config', 'config/ompl_planning.yaml'
    )
    ompl_planning_pipeline_config['move_group'].update(ompl_planning_yaml)

    # Controllers
    moveit_simple_controllers_yaml = load_yaml(
        'franka_robotiq_moveit_config', 'config/moveit_controllers.yaml'
    )
    moveit_controllers = {
        'moveit_simple_controller_manager': moveit_simple_controllers_yaml,
        'moveit_controller_manager': 'moveit_simple_controller_manager'
                                     '/MoveItSimpleControllerManager',
    }

    trajectory_execution = {
        'moveit_manage_controllers': True,
        'trajectory_execution.allowed_execution_duration_scaling': 1.2,
        'trajectory_execution.allowed_goal_duration_margin': 0.5,
        'trajectory_execution.allowed_start_tolerance': 0.01,
    }

    planning_scene_monitor_parameters = {
        'publish_planning_scene': True,
        'publish_geometry_updates': True,
        'publish_state_updates': True,
        'publish_transforms_updates': True,
    }

    # Move group node
    run_move_group_node = Node(
        package='moveit_ros_move_group',
        executable='move_group',
        output='screen',
        parameters=[
            robot_description,
            robot_description_semantic,
            kinematics_yaml,
            ompl_planning_pipeline_config,
            trajectory_execution,
            moveit_controllers,
            planning_scene_monitor_parameters,
        ],
    )

    # RViz
    rviz_base = os.path.join(get_package_share_directory('franka_moveit_config'), 'rviz')
    rviz_full_config = os.path.join(rviz_base, 'abhishek_diffusionsdf.rviz')

    rviz_node = Node(
        package='rviz2',
        executable='rviz2',
        name='rviz2',
        output='log',
        arguments=['-d', rviz_full_config],
        parameters=[
            robot_description,
            robot_description_semantic,
            ompl_planning_pipeline_config,
            kinematics_yaml,
        ],
    )

    # Robot state publisher
    robot_state_publisher = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        name='robot_state_publisher',
        output='both',
        parameters=[robot_description],
    )

    # Single ros2_control node for both Franka and Robotiq
    ros2_controllers_path = os.path.join(
        get_package_share_directory('franka_robotiq_moveit_config'),
        'config',
        'ros2_controllers.yaml',
    )

    # Add Robotiq update rate config
    robotiq_update_rate_config = os.path.join(
        get_package_share_directory('robotiq_description'),
        'config',
        'robotiq_update_rate.yaml',
    )

    ros2_control_node = Node(
        package='controller_manager',
        executable='ros2_control_node',
        parameters=[
            robot_description, 
            ros2_controllers_path,
            robotiq_update_rate_config
        ],
        remappings=[('joint_states', 'franka/joint_states')],
        output={
            'stdout': 'screen',
            'stderr': 'screen',
        },
        on_exit=Shutdown(),
    )

    # Load all controllers
    load_controllers = []
    controllers_to_load = [
        'robotiq_activation_controller',
        'robotiq_gripper_controller',
        # 'joint_trajectory_controller', 
        'joint_state_broadcaster'
    ]
    
    for controller in controllers_to_load:
        load_controllers.append(
            ExecuteProcess(
                cmd=['ros2 run controller_manager spawner {}'.format(controller)],
                shell=True,
                output='screen',
            )
        )

    # Warehouse mongodb server
    db_config = LaunchConfiguration('db')
    mongodb_server_node = Node(
        package='warehouse_ros_mongo',
        executable='mongo_wrapper_ros.py',
        parameters=[
            {'warehouse_port': 33829},
            {'warehouse_host': 'localhost'},
            {'warehouse_plugin': 'warehouse_ros_mongo::MongoDatabaseConnection'},
        ],
        output='screen',
        condition=IfCondition(db_config)
    )

    # Joint state publisher to combine joint states from different sources
    joint_state_publisher = Node(
        package='joint_state_publisher',
        executable='joint_state_publisher',
        name='joint_state_publisher',
        parameters=[
            {'source_list': ['panda/joint_states', 'gripper/joint_states'], 'rate': 30}
        ],
    )

    return LaunchDescription([
        robot_arg,
        use_fake_hardware_arg,
        fake_sensor_commands_arg,
        load_gripper_arg,
        com_port_arg,
        db_arg,
        rviz_node,
        robot_state_publisher,
        run_move_group_node,
        ros2_control_node,
        mongodb_server_node,
        joint_state_publisher,
    ] + load_controllers)