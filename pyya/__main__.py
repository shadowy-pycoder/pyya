import argparse
import logging
import sys

from pyya import PyyaError, init_config, logger


def main() -> None:
    parser = argparse.ArgumentParser(description='stub generator for pyya')
    parser.add_argument(
        '-i', '--input', default='default.config.yaml', help='path to YAML/TOML file from which to generate stub file'
    )
    parser.add_argument('-o', '--output', default='config.pyi', help='path to resulting stub pyi file')
    parser.add_argument('--var-name', default='config', help='variable name to refer to config object')
    parser.add_argument('--to-snake', action='store_true', help='convert config section names to snake case')
    parser.add_argument('--add-prefix', action='store_true', help='add underscore prefix to Python keywords')
    parser.add_argument('--replace-dashes', action='store_true', help='replace dashes with underscores in names')
    parser.add_argument('--debug', action='store_true', help='print debug messages')
    args = parser.parse_args()
    logger.setLevel(logging.INFO)
    if args.debug:
        logger.setLevel(logging.DEBUG)
    try:
        init_config(
            args.output,
            args.input,
            convert_keys_to_snake_case=args.to_snake,
            add_underscore_prefix_to_keywords=args.add_prefix,
            replace_dashes_with_underscores=args.replace_dashes,
            _generate_stub=True,
            _stub_variable_name=args.var_name,
        )
    except PyyaError:
        parser.print_usage()
        sys.exit(2)
    except Exception as e:
        print(repr(e))
        parser.print_usage()
        sys.exit(2)


if __name__ == '__main__':
    main()
