#!/usr/bin/env python3
"""
Generate config_stores.toml from .env.* files

Usage:
    python generate_config.py
    
This script scans for all .env.* files (excluding .env.example) and generates
a config_stores.toml file with the configuration for each store.
"""

import os
import glob
from pathlib import Path


def parse_env_file(filepath):
    """Parse a .env file and return a dictionary of key-value pairs."""
    config = {}
    with open(filepath, 'r') as f:
        for line in f:
            line = line.strip()
            # Skip comments and empty lines
            if not line or line.startswith('#'):
                continue
            
            # Parse KEY = VALUE format
            if '=' in line:
                key, value = line.split('=', 1)
                key = key.strip()
                value = value.strip()
                # Remove quotes if present
                if (value.startswith('"') and value.endswith('"')) or \
                   (value.startswith("'") and value.endswith("'")):
                    value = value[1:-1]
                config[key] = value
    
    return config


def get_store_title(store_name):
    """Generate a title from the store name."""
    # Remove 'af-' prefix if present
    name = store_name.replace('af-', '')
    # Capitalize first letter of each word
    return name.replace('-', ' ').title()


def generate_toml_config():
    """Generate config_stores.toml from all .env.* files."""
    script_dir = Path(__file__).parent
    
    # Find all .env.* files except .env.example
    env_files = glob.glob(str(script_dir / '.env.*'))
    env_files = [f for f in env_files if not f.endswith('.env.example')]
    
    if not env_files:
        print("No .env.* files found!")
        return
    
    # Sort files for consistent output
    env_files.sort()
    
    stores_config = {}
    
    for env_file in env_files:
        # Extract store identifier from filename (e.g., .env.murphy -> murphy)
        filename = Path(env_file).name
        store_id = filename.replace('.env.', '')
        
        # Parse the env file
        config = parse_env_file(env_file)
        
        if not config.get('STORE_NAME'):
            print(f"Warning: {filename} does not contain STORE_NAME, skipping...")
            continue
        
        # Create store config with TITLE
        store_config = {
            'TITLE': get_store_title(config.get('STORE_NAME', store_id)),
            'STORE_NAME': config.get('STORE_NAME', ''),
            'API_VERSION': config.get('API_VERSION', '2025-10'),
            'ACCESS_TOKEN': config.get('ACCESS_TOKEN', ''),
        }
        
        stores_config[store_id] = store_config
        print(f"✓ Loaded configuration for: {store_id}")
    
    # Generate TOML content
    toml_content = "[stores]\n"
    
    for store_id, config in stores_config.items():
        toml_content += f"\n[stores.{store_id}]\n"
        toml_content += f'TITLE = "{config["TITLE"]}"\n'
        toml_content += f'STORE_NAME = "{config["STORE_NAME"]}"\n'
        toml_content += f"API_VERSION = '{config['API_VERSION']}'\n"
        toml_content += f'ACCESS_TOKEN = "{config["ACCESS_TOKEN"]}"\n'
    
    # Write to config_stores.toml
    output_file = script_dir / 'config_stores.toml'
    with open(output_file, 'w') as f:
        f.write(toml_content)
    
    print(f"\n✅ Successfully generated {output_file}")
    print(f"   Total stores configured: {len(stores_config)}")


if __name__ == '__main__':
    generate_toml_config()
