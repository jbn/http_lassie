from distutils.core import setup

setup(
    name="http_lassie",
    version="0.0.1",
    packages=["http_lassie"],
    license="License :: OSI Approved :: MIT License",
    author="John Bjorn Nelson",
    author_email="jbn@abreka.com",
    description="Fetch Lassie.",
    long_description="JS rendering proxy brokered requesting",
    url="https://github.com/jbn/mimic",
    package_data={'http_lassie': ['user_agents.tsv']},
)
