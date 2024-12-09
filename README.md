# pyya - Simple tool that converts YAML configuration files to Python objects

![PyPI - Downloads](https://img.shields.io/pypi/dd/pyya)
[![ClickPy Dashboard](https://img.shields.io/badge/clickpy-dashboard-orange)](https://clickpy.clickhouse.com/dashboard/pyya)
![PyPI - Python Version](https://img.shields.io/pypi/pyversions/pyya)
[![PyPI - Link](https://img.shields.io/badge/pypi-link-blue)](https://pypi.org/project/pyya/)
![PyPI - Version](https://img.shields.io/pypi/v/pyya)
![PyPI - Wheel](https://img.shields.io/pypi/wheel/pyya)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)

## Features

- Very `lightweight` and `simple` API (currently it contains only one function)
- `Easy` to use
- Based on popular and well-tested libraries (like `camel-converter`, `PyYAML` and `munch`)
- Automatically `merge` default and production configuration files
- Convert keys in configuration files to `snake_case`


## Installation

```shell
pip install pyya
```

## Usage

### Example

Create YAML configuration files for your project:

```yaml
# default.config.yaml - this file usually goes to version control system
database:   
    host: localhost
    port: 5432
    username: postgres
    password: postgres
```

```yaml
# config.yaml - this file for production usage
database:   
    username: username
    password: password
```

Import configuration files in your Python code with pyya:

```python
import json

from pyya import init_config

config = init_config(
    'config.yaml', 'default.config.yaml', 
    convert_keys_to_snake_case = False,
    add_underscore_prefix_to_keywords = False
    raise_error_non_identifiers = False)
print(json.dumps(config.database))

# Output:
# {"host": "localhost", "port": 5432, "username": "username", "password": "password"}

```

As you can see, `pyya` automatically merges default config file with production config file.

Under the hood `pyya` uses [PyYAML](https://pypi.org/project/PyYAML/) to parse YAML files and [munch](https://pypi.org/project/munch/) library to create attribute-stylish dictionaries.

 and can be configured to . 

### Flags

```python 
convert_keys_to_snake_case=True 
# `pyya` converts `camelCase` or `PascalCase` keys to `snake_case`
``` 

```python 
add_underscore_prefix_to_keywords=True 
# `pyya` adds underscore prefix to keys that are Python keywords
``` 

```python 
raise_error_non_identifiers=True 
# `pyya` raises error if key name is not valid Python identifier
```

## Contributing

Are you a developer?

- Fork the repository `https://github.com/shadowy-pycoder/pyya/fork`
- Clone the repository: `git clone https://github.com/<your-username>/pyya.git && cd pyya`
- Create your feature branch: `git switch -c my-new-feature`
- Commit your changes: `git commit -am 'Add some feature'`
- Push to the branch: `git push origin my-new-feature`
- Submit a pull request
