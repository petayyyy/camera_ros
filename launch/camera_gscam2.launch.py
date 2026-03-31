"""
GStreamer-based camera launch для Radxa CM5 (RK3588S).

Замена camera.launch.py для платформ с vendor-ядром Rockchip (rkisp1-vir0),
где upstream libcamera не может обнаружить камеру.

Публикует те же топики и TF что camera.launch.py:
  /<namespace>/image_raw
  /<namespace>/camera_info
  TF: base_link → camera_optical_<id>

Использование:
  ros2 launch camera_ros camera_gscam2.launch.py sensor:=imx219 width:=640 height:=480 fps:=25 camera_id:=1
  ros2 launch camera_ros camera_gscam2.launch.py sensor:=ov5647 width:=320 height:=240 fps:=25 camera_id:=1
"""

import os
import sys
import yaml
from launch import LaunchDescription
from launch_ros.actions import Node
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition
from launch.substitutions import (
    LaunchConfiguration,
    PythonExpression,
    TextSubstitution,
    EqualsSubstitution,
)


def generate_launch_description():
    launch_dir = os.path.dirname(os.path.abspath(__file__))
    src_config_dir = os.path.abspath(os.path.join(launch_dir, '..', 'config'))

    # ------------------------------------------------------------------
    # Загрузка camera_tf из params.yaml (та же логика что в camera.launch.py)
    # ------------------------------------------------------------------
    camera_tfs = {}
    params_path = os.path.join(src_config_dir, 'params.yaml')
    print(f"[camera_gscam2.launch] Loading params from: {params_path}", file=sys.stderr)
    if os.path.exists(params_path):
        try:
            with open(params_path, 'r') as f:
                cfg = yaml.safe_load(f) or {}
            for i in range(3):
                key = f'camera_tf_{i}'
                src = cfg.get(key, {}).get('ros__parameters', {})
                camera_tfs[str(i)] = {
                    'parent_frame': str(src.get('parent_frame', 'base_link')),
                    'xyz': [str(x) for x in src.get('xyz', [0.0, 0.0, 0.0])],
                    'rpy': [str(r) for r in src.get('rpy', [0.0, 0.0, 0.0])],
                }
        except Exception as e:
            print(f"[camera_gscam2.launch] Error loading params.yaml: {e}", file=sys.stderr)

    # ------------------------------------------------------------------
    # Launch arguments (совместимы с camera.launch.py)
    # ------------------------------------------------------------------
    ld_items = [
        DeclareLaunchArgument('sensor', default_value='ov5647'),
        DeclareLaunchArgument('width', default_value='640'),
        DeclareLaunchArgument('height', default_value='320'),
        DeclareLaunchArgument('fps', default_value='25'),
        DeclareLaunchArgument('camera', default_value='0'),
        DeclareLaunchArgument('camera_id', default_value=LaunchConfiguration('camera')),
        DeclareLaunchArgument('video_device', default_value='/dev/video11',
                              description='V4L2 capture device (rkisp_mainpath)'),
    ]

    sensor_type = LaunchConfiguration('sensor')
    width = LaunchConfiguration('width')
    height = LaunchConfiguration('height')
    fps = LaunchConfiguration('fps')
    camera_id = LaunchConfiguration('camera_id')
    video_device = LaunchConfiguration('video_device')

    # ------------------------------------------------------------------
    # Путь к калибровочному YAML
    # ------------------------------------------------------------------
    calib_filename = PythonExpression([
        "f'file://", TextSubstitution(text=src_config_dir), "/",
        "' + str('", sensor_type, "') + '_' + str('", width, "') + 'x' + str('", height, "') + '.yaml'"
    ])

    # ------------------------------------------------------------------
    # GStreamer pipeline
    # ------------------------------------------------------------------
    # v4l2src прозрачно работает с V4L2 MPLANE (rkisp_mainpath).
    # do-timestamp=true — GStreamer генерирует таймстемпы для каждого буфера.
    # videoconvert — NV12 из ISP конвертируется в формат, согласованный gscam2.
    # НЕ добавлять appsink — gscam2 добавляет его сам внутри create_pipeline().
    gscam_config = PythonExpression([
        "f'v4l2src device=", video_device,
        " do-timestamp=true"
        " ! video/x-raw,format=NV12,width=", width,
        ",height=", height,
        " ! videoconvert'"
    ])

    # ------------------------------------------------------------------
    # gscam2 node
    # ------------------------------------------------------------------
    # Namespace /camera_{id} — топики: /camera_{id}/image_raw, /camera_{id}/camera_info
    ld_items.append(
        Node(
            package='gscam2',
            executable='gscam_main',
            name=sensor_type,
            namespace=[TextSubstitution(text='camera_'), camera_id],
            parameters=[{
                'gscam_config': gscam_config,
                'camera_name': sensor_type,
                'camera_info_url': calib_filename,
                'frame_id': [TextSubstitution(text='camera_optical_'), camera_id],
            }],
            # gscam2 публикует ~/image_raw → переименуем в image_raw (без node name prefix)
            remappings=[
                ('~/image_raw', 'image_raw'),
                ('~/camera_info', 'camera_info'),
            ],
            output='screen',
        )
    )

    # ------------------------------------------------------------------
    # Статический TF (та же логика что в camera.launch.py)
    # ------------------------------------------------------------------
    for cam_id, tf_cfg in camera_tfs.items():
        ld_items.append(
            Node(
                package='tf2_ros',
                executable='static_transform_publisher',
                name=[TextSubstitution(text='camera_tf_'), TextSubstitution(text=cam_id)],
                condition=IfCondition(
                    EqualsSubstitution(camera_id, cam_id)
                ),
                arguments=[
                    tf_cfg['xyz'][0],
                    tf_cfg['xyz'][1],
                    tf_cfg['xyz'][2],
                    tf_cfg['rpy'][0],
                    tf_cfg['rpy'][1],
                    tf_cfg['rpy'][2],
                    tf_cfg['parent_frame'],
                    [TextSubstitution(text='camera_optical_'), camera_id],
                ],
                output='screen',
            )
        )

    return LaunchDescription(ld_items)
