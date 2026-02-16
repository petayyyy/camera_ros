import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch_ros.actions import Node
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution, TextSubstitution

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

    return LaunchDescription([
        DeclareLaunchArgument('sensor', default_value='ov5647'),
        DeclareLaunchArgument('width', default_value='640'),
        DeclareLaunchArgument('height', default_value='480'),
        DeclareLaunchArgument('fps_limit', default_value='[16666, 16666]'),
        DeclareLaunchArgument('camera', default_value='0'),

        Node(
            package='camera_ros',
            executable='camera_node',
            name=sensor_type,
            parameters=[
                os.path.join(pkg_share, 'config', 'params.yaml'),  # из install (можно заменить)
                {
                    'camera': LaunchConfiguration('camera'),
                    'width': width,
                    'height': height,
                    'FrameDurationLimits': LaunchConfiguration('fps_limit'),
                    'camera_info_url': calib_url,
                }
            ],
            output='screen'
        )
    ])