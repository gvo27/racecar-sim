from setuptools import find_packages, setup

package_name = 'rccar_sim_mcu'

setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/rccar_sim_mcu']),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='gvo27',
    maintainer_email='gvo@berkeley.edu',
    description='Virtual ESP32 for the sim: the firmware model and the /rccar/mcu/* node.',
    license='MIT',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [],
    },
)
