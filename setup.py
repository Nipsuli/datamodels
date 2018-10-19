from setuptools import setup

with open('README.md', 'r', encoding='utf8') as f:
    readme = f.read()

setup(name='datamodels',
      version='0.0.1',
      description='JSON (De)Serialization for python 3.7 dataclasses',
      long_description=readme,
      long_description_content_type='text/markdown',
      url='https://github.com/Nipsuli/datamodels',
      author='Niko Ahonen',
      author_email='n.p.ahonen@gmail.com',
      license='MIT',
      packages=['datamodels'],
      install_requires=["dataclasses;python_version=='3.7'"],
      python_requires=">=3.7",
      keywords="dataclasses json",
      setup_requires=["pytest-runner"],
      tests_require=["pytest"]
)
