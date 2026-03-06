import os
import yaml
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch_ros.actions import Node
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition
from launch.substitutions import (
    LaunchConfiguration,
    PathJoinSubstitution,
    TextSubstitution,
    PythonExpression,
)


def generate_launch_description():
    # ------------------------------------------------------------
    # 1. Определяем путь к директории config в исходниках пакета
    #    (предполагается, что launch-файл лежит в camera_ros/launch/)
    # ------------------------------------------------------------
    launch_dir = os.path.dirname(os.path.abspath(__file__))
    src_config_dir = os.path.join(launch_dir, '..', 'config')
    # Нормализуем путь (убираем лишние '..')
    src_config_dir = os.path.abspath(src_config_dir)

    # ------------------------------------------------------------
    # 2. Параметры из install (можно оставить или тоже перевести на src)
    # ------------------------------------------------------------
    pkg_share = get_package_share_directory('camera_ros')

    sensor_type = LaunchConfiguration('sensor')
    width = LaunchConfiguration('width')
    height = LaunchConfiguration('height')

    # Формируем имя файла калибровки: sensor_widthxheight.yaml
    calib_file = [sensor_type, TextSubstitution(text='_'), width,
                  TextSubstitution(text='x'), height, TextSubstitution(text='.yaml')]

    # Собираем полный путь к файлу калибровки в src-конфиге
    calib_path = PathJoinSubstitution([TextSubstitution(text=src_config_dir), calib_file])
    calib_url = [TextSubstitution(text='file://'), calib_path]

    # ------------------------------------------------------------
    # 3. Читаем параметры TF камеры из params.yaml
    #    Поддерживаются camera_tf_0, camera_tf_1, camera_tf_2
    # ------------------------------------------------------------
    camera_tfs = {}
    params_path = os.path.join(src_config_dir, 'params.yaml')
    if os.path.exists(params_path):
        try:
            with open(params_path, 'r') as f:
                cfg = yaml.safe_load(f) or {}
            # базовое значение по умолчанию
            default_parent = 'base_link'
            default_xyz = ['0.0', '0.0', '0.0']
            default_rpy = ['0.0', '0.0', '0.0']
            # поддерживаем до 3 камер: 0, 1, 2
            for i in range(3):
                key = f'camera_tf_{i}'
                src_node = cfg.get(key, {})
                src = src_node.get('ros__parameters', {})
                parent = src.get('parent_frame', default_parent)
                xyz = src.get('xyz', default_xyz)
                rpy = src.get('rpy', default_rpy)
                camera_tfs[str(i)] = {
                    'parent_frame': str(parent),
                    'xyz': [str(x) for x in xyz],
                    'rpy': [str(r) for r in rpy],
                }
        except Exception:
            # при ошибке просто оставим значения по умолчанию
            camera_tfs = {}

    ld_items = [
        DeclareLaunchArgument('sensor', default_value='ov5647'),
        DeclareLaunchArgument('width', default_value='640'),
        DeclareLaunchArgument('height', default_value='320'),
        DeclareLaunchArgument('fps', default_value='25'),
        DeclareLaunchArgument('camera', default_value='0'),
        DeclareLaunchArgument('camera_id', default_value=LaunchConfiguration('camera')),

        Node(
            package='camera_ros',
            executable='camera_node',
            name=sensor_type,
            namespace=[TextSubstitution(text='camera_'), LaunchConfiguration('camera_id')],
                parameters=[
                os.path.join(pkg_share, 'config', 'params.yaml'),
                {
                    # Передаём в узел 0-based индекс камеры (libcamera): camera_id 1 → индекс 0
                    'camera': PythonExpression(['str(max(0, int(', LaunchConfiguration('camera_id'), ') - 1))']),
                    'width': width,
                    'height': height,
                    # Длительность кадра в µs: (1/fps)*1e6. Без нижнего порога — макс. fps задаётся только камерой и разрешением.
                    'FrameDurationLimits': PythonExpression([
                        '"[" + '
                        'str(int(1.0/float(', LaunchConfiguration('fps'), ')*1e6)) '
                        '+ ", " + '
                        'str(int(1.0/float(', LaunchConfiguration('fps'), ')*1e6)) '
                        '+ "]"'
                    ]),
                    'camera_info_url': calib_url,
                    'frame_id': [TextSubstitution(text='camera_optical_'), LaunchConfiguration('camera_id')],
                    'topic_base': PythonExpression(["'/camera_' + str(", LaunchConfiguration('camera_id'), ")"])
                }
            ],
            output='screen'
        ),
    ]

    # Публикация статического TF камеры относительно дрона
    for cam_id, tf_cfg in camera_tfs.items():
        ld_items.append(
            Node(
                package='tf2_ros',
                executable='static_transform_publisher',
                name=[TextSubstitution(text='camera_tf_'), TextSubstitution(text=cam_id)],
                condition=IfCondition(
                    PythonExpression([
                        LaunchConfiguration('camera_id'),
                        ' == "',
                        cam_id,
                        '"',
                    ])
                ),
                arguments=[
                    tf_cfg['xyz'][0],
                    tf_cfg['xyz'][1],
                    tf_cfg['xyz'][2],
                    tf_cfg['rpy'][0],
                    tf_cfg['rpy'][1],
                    tf_cfg['rpy'][2],
                    tf_cfg['parent_frame'],
                    [TextSubstitution(text='camera_optical_'), LaunchConfiguration('camera_id')],
                ],
                output='screen'
            )
        )

    return LaunchDescription(ld_items)