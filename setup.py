from setuptools import find_packages, setup

setup(
    name='netbox_golden_config',
    version='0.1',
    description='App that provides a NetDevOps approach to golden configuration and configuration compliance',
    install_requires=[],
    author = "Alexey Tokarev",
    packages=find_packages(),
    include_package_data=True,
    zip_safe=False,
)