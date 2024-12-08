# paya - Simple tool that converts YAML configuration files to Python objects

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)


## Installation

```shell
pip install pyya
```

## Usage

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
    raise_error_non_identifiers = False)
print(json.dumps(config.database))

# Output:
# {"host": "localhost", "port": 5432, "username": "username", "password": "password"}

```

As you can see, pyya automatically merges default config file with production config file.

Under the hood `pyya` uses [munch](https://pypi.org/project/munch/) library to create attribute-stylish dictionaries.

`paya` automatically adds underscore prefix to Python keywords and can be configured to convert `camelCase` or `PascalCase` keys to snake_case. 

If `raise_error_non_identifiers` is True, `pyya` will raise error if section name is not valid Python identifier.

## Contributing

Are you a developer?

- Fork the repository
- Create your feature branch: `git switch -c my-new-feature`
- Commit your changes: `git commit -am 'Add some feature'`
- Push to the branch: `git push origin my-new-feature`
- Submit a pull request
